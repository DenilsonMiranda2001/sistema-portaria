import psycopg2
import psycopg2.pool
import threading
import logging
from psycopg2.extras import RealDictCursor
from config import Config

_pool = None
_pool_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _connection_kwargs():
    if Config.DATABASE_URL:
        return {"dsn": Config.DATABASE_URL}
    return {
        "host": Config.DB_HOST,
        "database": Config.DB_NAME,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
        "port": Config.DB_PORT,
    }


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=Config.DB_POOL_MIN,
                    maxconn=Config.DB_POOL_MAX,
                    connect_timeout=10,
                    application_name="sistema-portaria",
                    **_connection_kwargs(),
                )
                logger.info("PostgreSQL pool initialized min=%s max=%s", Config.DB_POOL_MIN, Config.DB_POOL_MAX)
    return _pool


def conectar_dedicado(application_name="sistema-portaria-maintenance"):
    conn = psycopg2.connect(
        connect_timeout=10,
        application_name=application_name,
        cursor_factory=RealDictCursor,
        **_connection_kwargs(),
    )
    return conn


def conectar():
    conn = _get_pool().getconn()
    conn.cursor_factory = RealDictCursor
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '15s'")
        cur.execute("SET idle_in_transaction_session_timeout = '30s'")
    conn.commit()
    return conn


def liberar(conn):
    if conn is None:
        return
    try:
        if not conn.closed and conn.get_transaction_status() != 0:
            conn.rollback()
    finally:
        _get_pool().putconn(conn)


def verificar_conexao():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1
    finally:
        liberar(conn)
