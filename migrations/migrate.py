import argparse
import hashlib
from pathlib import Path
from database.connection import conectar, liberar

MIGRATIONS_DIR = Path(__file__).resolve().parent
BASE_SCHEMA = MIGRATIONS_DIR.parent / "database" / "schema.sql"


def migrate():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.usuarios') AS usuarios")
            if not cur.fetchone()["usuarios"]:
                cur.execute(BASE_SCHEMA.read_text(encoding="utf-8"))
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    checksum VARCHAR(64) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()

        for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            with conn.cursor() as cur:
                cur.execute("SELECT checksum FROM schema_migrations WHERE version=%s", (path.name,))
                existing = cur.fetchone()
                if existing:
                    if existing["checksum"] != checksum:
                        raise RuntimeError(f"Migration checksum mismatch: {path.name}")
                    continue
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations(version, checksum) VALUES (%s,%s)",
                    (path.name, checksum),
                )
            conn.commit()
            print(f"applied {path.name}")
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["upgrade"])
    args = parser.parse_args()
    if args.command == "upgrade":
        migrate()
