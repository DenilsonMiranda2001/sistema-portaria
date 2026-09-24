from database.connection import conectar_dedicado


def database_ready() -> bool:
    conn = None
    try:
        conn = conectar_dedicado("controleid-hardware-health")
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def main():
    raise SystemExit(0 if database_ready() else 1)


if __name__ == "__main__":
    main()
