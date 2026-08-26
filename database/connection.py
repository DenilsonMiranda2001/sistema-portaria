import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from config import Config

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT,
        )
    return _pool


def conectar():
    conn = _get_pool().getconn()
    conn.cursor_factory = RealDictCursor
    return conn


def liberar(conn):
    _get_pool().putconn(conn)
