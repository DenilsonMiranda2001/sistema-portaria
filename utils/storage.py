import base64
import io
import os
import uuid
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from werkzeug.utils import secure_filename

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}


def _extension(filename):
    ext = Path(secure_filename(filename or "")).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError("Formato de imagem não permitido.")
    return ext


def save_image(file_storage, tenant_id):
    ext = _extension(file_storage.filename)
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
        ExtraArgs={"ContentType": file_storage.mimetype or "application/octet-stream"},
    )
    return key


def save_webcam_image(data_url, tenant_id):
    prefix = "data:image/jpeg;base64,"
    if not data_url or not data_url.startswith(prefix):
        raise ValueError("Captura de webcam inválida.")
    try:
        raw = base64.b64decode(data_url[len(prefix):], validate=True)
    except Exception as exc:
        raise ValueError("Captura de webcam inválida.") from exc
    if not raw or len(raw) > 5 * 1024 * 1024 or not raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("Imagem de webcam inválida ou muito grande.")
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
