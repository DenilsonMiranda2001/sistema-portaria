import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-only-secret-not-for-production" if os.getenv("APP_ENV", "development").lower() != "production" else None)

    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "portaria_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

    UPLOAD_FOLDER = os.path.join("static", "fotos")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", APP_ENV == "production")
    SESSION_REFRESH_EACH_REQUEST = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    @classmethod
    def validate(cls):
        if cls.APP_ENV == "production":
            if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
                raise RuntimeError("SECRET_KEY must be configured with at least 32 characters in production.")
            if not cls.DATABASE_URL and (not cls.DB_HOST or not cls.DB_NAME or not cls.DB_USER):
                raise RuntimeError("Database configuration is incomplete.")
            storage_vars = ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
            missing_storage = [name for name in storage_vars if not os.getenv(name)]
            if missing_storage:
                raise RuntimeError("Private object storage configuration is incomplete: " + ", ".join(missing_storage))
            audit_salt = os.getenv("AUDIT_IP_SALT", "")
            if len(audit_salt) < 16:
                raise RuntimeError("AUDIT_IP_SALT must be configured with at least 16 characters in production.")
