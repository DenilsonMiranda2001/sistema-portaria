import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from config import Config

_pool = None


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
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=Config.DB_POOL_MIN,
            maxconn=Config.DB_POOL_MAX,
            connect_timeout=10,
            application_name="sistema-portaria",
            **_connection_kwargs(),
        )
    return _pool


def conectar():
    conn = _get_pool().getconn()
    conn.cursor_factory = RealDictCursor
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
