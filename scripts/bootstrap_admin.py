import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from werkzeug.security import generate_password_hash
from database.connection import conectar, liberar


def main():
    parser = argparse.ArgumentParser(description="Create or update the global platform administrator.")
    parser.add_argument("--username", default=os.getenv("BOOTSTRAP_ADMIN_USERNAME"))
    args = parser.parse_args()
    username = (args.username or input("Username: ")).strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if not username or len(password) < 12:
        raise SystemExit("Username is required and password must have at least 12 characters.")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO platform_admins (nome, usuario, senha, ativo)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (usuario)
                DO UPDATE SET senha=EXCLUDED.senha, ativo=TRUE, atualizado_em=CURRENT_TIMESTAMP
                RETURNING id
            """, ("ADMINISTRADOR GERAL", username, generate_password_hash(password)))
            cur.fetchone()
        conn.commit()
        print("Platform administrator bootstrap completed successfully.")
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


if __name__ == "__main__":
    main()
