"""One-shot PostgreSQL logical backup to a private, dedicated S3-compatible bucket.

Run in a separate Railway job with pg_dump installed. No production mutations.
Never log connection strings, object credentials, or dump contents.
"""
import hashlib
import json
import os
import subprocess  # nosec B404 - backup job runs fixed PostgreSQL tools without a shell
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit, unquote, parse_qs

import boto3
from botocore.config import Config as BotoConfig


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required backup configuration: {name}")
    return value


def run():
    database_url = required("BACKUP_DATABASE_URL")
    endpoint = required("BACKUP_R2_ENDPOINT")
    bucket = required("BACKUP_R2_BUCKET")
    key_id = required("BACKUP_R2_ACCESS_KEY_ID")
    secret = required("BACKUP_R2_SECRET_ACCESS_KEY")
    if not endpoint.startswith("https://"):
        raise RuntimeError("BACKUP_R2_ENDPOINT must use HTTPS")
    if os.environ.get("BACKUP_CONFIRM_ISOLATED_BUCKET") != "yes":
        raise RuntimeError("Explicit confirmation of dedicated private backup bucket required")
    if os.environ.get("BACKUP_ENVIRONMENT") not in ("staging", "production"):
        raise RuntimeError("BACKUP_ENVIRONMENT must be staging or production")

    now = datetime.now(timezone.utc)
    backup_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    prefix = f"postgres/{os.environ['BACKUP_ENVIRONMENT']}/{now:%Y/%m/%d}/{backup_id}"
    client = boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=key_id,
        aws_secret_access_key=secret, region_name="auto",
        config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
    )
    # Resolve trusted executables before invoking them; never pass user input as a command.
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise RuntimeError("PostgreSQL backup tools pg_dump and pg_restore are required")
    with tempfile.TemporaryDirectory(prefix="controleid-backup-") as directory:
        dump = Path(directory) / "database.dump"
        # Pass the DSN via environment rather than command arguments.
        parsed = urlsplit(database_url)
        if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname or not parsed.path.strip("/"):
            raise RuntimeError("BACKUP_DATABASE_URL must be a PostgreSQL connection URL")
        params = parse_qs(parsed.query)
        env = dict(os.environ, PGCONNECT_TIMEOUT="15",
                   PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
                   PGUSER=unquote(parsed.username or ""),
                   PGPASSWORD=unquote(parsed.password or ""),
                   PGDATABASE=unquote(parsed.path.lstrip("/")),
                   PGSSLMODE=params.get("sslmode", ["prefer"])[0])
        env.pop("BACKUP_DATABASE_URL", None)
        subprocess.run(
            [pg_dump, "--format=custom", "--no-owner", "--no-acl",
             "--file", str(dump)],
            env=env, check=True, timeout=3600, stdout=subprocess.DEVNULL,  # nosec B603 - fixed executable and arguments; no shell
        )
        size = dump.stat().st_size
        if size == 0:
            raise RuntimeError("pg_dump produced an empty file")
        digest = hashlib.sha256()
        with dump.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        subprocess.run([pg_restore, "--list", str(dump)], check=True,  # nosec B603 - fixed executable and arguments; no shell
                       stdout=subprocess.DEVNULL, timeout=120)
        object_key = prefix + "/database.dump"
        client.upload_file(str(dump), bucket, object_key)
        metadata = client.head_object(Bucket=bucket, Key=object_key)
        if metadata["ContentLength"] != size:
            raise RuntimeError("Uploaded backup size mismatch")
        manifest = {
            "schema": "controleid-postgres-backup/v1",
            "backup_id": backup_id,
            "environment": os.environ["BACKUP_ENVIRONMENT"],
            "created_at": now.isoformat(),
            "object_key": object_key,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "format": "pg_dump-custom",
            "verification": "pg_restore-list-and-remote-size",
        }
        # Manifest is written only after successful upload and checks.
        client.put_object(
            Bucket=bucket, Key=prefix + "/manifest.json",
            Body=json.dumps(manifest, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
        print(json.dumps({"result": "backup_uploaded", "backup_id": backup_id,
                          "bytes": size, "environment": manifest["environment"]}))


if __name__ == "__main__":
    run()
