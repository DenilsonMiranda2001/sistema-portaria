import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret-troque-em-producao"

    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_NAME     = os.getenv("DB_NAME", "portaria_db")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_PORT     = os.getenv("DB_PORT", "5432")

    UPLOAD_FOLDER     = os.path.join("static", "fotos")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB máximo por upload

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Em produção: SESSION_COOKIE_SECURE = True (requer HTTPS)
