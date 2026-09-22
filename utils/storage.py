import base64
import io
import os
import uuid
from pathlib import Path

import boto3
from PIL import Image, UnidentifiedImageError
from botocore.config import Config as BotoConfig
from werkzeug.utils import secure_filename

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_EXTENSIONS = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"}}
FORMAT_MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_SIDE = 8_000


def _validate_dimensions(image):
    width, height = image.size
    if width <= 0 or height <= 0 or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("Dimensões da imagem excedem o limite permitido.")


def _require_tenant(tenant_id):
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError("Contexto de condomínio inválido.")


def _validated_upload(file_storage):
    ext = _extension(file_storage.filename)
    stream = file_storage.stream
    try:
        stream.seek(0)
        image = Image.open(stream)
        _validate_dimensions(image)
        image.verify()
        fmt = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Arquivo enviado não é uma imagem válida.") from exc
    finally:
        stream.seek(0)
    if fmt not in FORMAT_EXTENSIONS or ext not in FORMAT_EXTENSIONS[fmt]:
        raise ValueError("Extensão da imagem não corresponde ao conteúdo do arquivo.")
    return ext, FORMAT_MIMES[fmt]


def _extension(filename):
    ext = Path(secure_filename(filename or "")).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError("Formato de imagem não permitido.")
    return ext


def save_image(file_storage, tenant_id):
    _require_tenant(tenant_id)
    ext, content_type = _validated_upload(file_storage)
    key = f"condominios/{tenant_id}/visitantes/{uuid.uuid4().hex}{ext}"
    endpoint = os.getenv("S3_ENDPOINT_URL")
    bucket = os.getenv("S3_BUCKET")
    if not endpoint or not bucket:
        raise RuntimeError("Object storage is not configured")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
        config=BotoConfig(signature_version="s3v4"),
    )
    client.upload_fileobj(
        file_storage.stream,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def save_webcam_image(data_url, tenant_id):
    _require_tenant(tenant_id)
    prefix = "data:image/jpeg;base64,"
    if not data_url or not data_url.startswith(prefix):
        raise ValueError("Captura de webcam inválida.")
    try:
        raw = base64.b64decode(data_url[len(prefix):], validate=True)
    except Exception as exc:
        raise ValueError("Captura de webcam inválida.") from exc
    if not raw or len(raw) > 5 * 1024 * 1024 or not raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("Imagem de webcam inválida ou muito grande.")
    try:
        image = Image.open(io.BytesIO(raw))
        _validate_dimensions(image)
        image.verify()
        if image.format != "JPEG":
            raise ValueError("Captura de webcam inválida.")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Captura de webcam inválida.") from exc
    key = f"condominios/{tenant_id}/visitantes/{uuid.uuid4().hex}.jpg"
    endpoint = os.getenv("S3_ENDPOINT_URL")
    bucket = os.getenv("S3_BUCKET")
    if not endpoint or not bucket:
        raise RuntimeError("Object storage is not configured")
    client = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
        config=BotoConfig(signature_version="s3v4"),
    )
    client.upload_fileobj(io.BytesIO(raw), bucket, key, ExtraArgs={"ContentType": "image/jpeg"})
    return key


def presigned_image_url(key, expires=300):
    endpoint = os.getenv("S3_ENDPOINT_URL")
    bucket = os.getenv("S3_BUCKET")
    if not endpoint or not bucket or not key:
        raise RuntimeError("Object storage is not configured")
    client = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
        config=BotoConfig(signature_version="s3v4"),
    )
    return client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)


def delete_image(object_key):
    if not object_key:
        return
    client, bucket = _client()
    client.delete_object(Bucket=bucket, Key=object_key)
