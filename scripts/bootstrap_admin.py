import argparse
import getpass
import os
from werkzeug.security import generate_password_hash
from database.connection import conectar, liberar


def main():
    parser = argparse.ArgumentParser(description="Create or update the first tenant administrator.")
    parser.add_argument("--username", default=os.getenv("BOOTSTRAP_ADMIN_USERNAME"))
    parser.add_argument("--tenant-slug", default=os.getenv("BOOTSTRAP_TENANT_SLUG", "condominio-inicial"))
    args = parser.parse_args()
    username = (args.username or input("Username: ")).strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if not username or len(password) < 12:
        raise SystemExit("Username is required and password must have at least 12 characters.")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM condominios WHERE slug=%s AND ativo=TRUE", (args.tenant_slug,))
            tenant = cur.fetchone()
            if not tenant:
                raise SystemExit("Active tenant not found.")
            cur.execute("""
                INSERT INTO usuarios (condominio_id, nome, usuario, senha, nivel, ativo)
                VALUES (%s, %s, %s, %s, 'admin', TRUE)
                ON CONFLICT (condominio_id, usuario) WHERE condominio_id IS NOT NULL
                DO UPDATE SET senha=EXCLUDED.senha, nivel='admin', ativo=TRUE
                RETURNING id
            """, (tenant["id"], "ADMINISTRADOR GERAL", username, generate_password_hash(password)))
            user = cur.fetchone()
        conn.commit()
        print("Administrator bootstrap completed successfully.")
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


if __name__ == "__main__":
    main()
