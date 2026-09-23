"""Read-only release preflight for an isolated staging/restored database.

Requires explicit acknowledgement and refuses production. Exit nonzero on anomalies.
"""
import os
import hashlib
from pathlib import Path
from database.connection import conectar_dedicado


CHECKS = {
    "unexpected_tenant_roles": """SELECT COUNT(*) AS n FROM usuarios
        WHERE nivel NOT IN ('admin_condominio','administrativo','porteiro')""",
    "tenant_users_without_condominium": """SELECT COUNT(*) AS n FROM usuarios
        WHERE condominio_id IS NULL""",
    "active_condominiums_without_active_admin": """SELECT COUNT(*) AS n FROM condominios c
        WHERE c.ativo AND EXISTS (SELECT 1 FROM usuarios existing WHERE existing.condominio_id=c.id) AND NOT EXISTS (
            SELECT 1 FROM usuarios u WHERE u.condominio_id=c.id
              AND u.ativo AND u.nivel='admin_condominio'
        )""",
    "visitor_tenant_mismatch": """SELECT COUNT(*) AS n FROM visitas vi
        JOIN visitantes v ON v.id=vi.visitante_id
        WHERE vi.condominio_id IS DISTINCT FROM v.condominio_id""",
    "visit_entry_user_tenant_mismatch": """SELECT COUNT(*) AS n FROM visitas vi
        JOIN usuarios u ON u.id=vi.usuario_entrada_id
        WHERE vi.condominio_id IS DISTINCT FROM u.condominio_id""",
    "visit_exit_user_tenant_mismatch": """SELECT COUNT(*) AS n FROM visitas vi
        JOIN usuarios u ON u.id=vi.usuario_saida_id
        WHERE vi.condominio_id IS DISTINCT FROM u.condominio_id""",
    "parcel_lot_tenant_mismatch": """SELECT COUNT(*) AS n FROM encomendas e
        JOIN lotes_encomendas l ON l.id=e.lote_id
        WHERE e.condominio_id IS DISTINCT FROM l.condominio_id""",
    "parcel_resident_tenant_mismatch": """SELECT COUNT(*) AS n FROM encomendas e
        JOIN moradores m ON m.id=e.morador_id
        WHERE e.condominio_id IS DISTINCT FROM m.condominio_id""",
    "parcel_creator_tenant_mismatch": """SELECT COUNT(*) AS n FROM encomendas e
        JOIN usuarios u ON u.id=e.usuario_criacao_id
        WHERE e.condominio_id IS DISTINCT FROM u.condominio_id""",
    "courier_lot_tenant_mismatch": """SELECT COUNT(*) AS n FROM lotes_encomendas l
        JOIN entregadores e ON e.id=l.entregador_id
        WHERE l.condominio_id IS DISTINCT FROM e.condominio_id""",
    "resident_unit_tenant_mismatch": """SELECT COUNT(*) AS n FROM moradores m
        JOIN unidades u ON u.id=m.unidade_id
        WHERE m.condominio_id IS DISTINCT FROM u.condominio_id""",
    "visit_unit_tenant_mismatch": """SELECT COUNT(*) AS n FROM visitas vi
        JOIN unidades u ON u.id=vi.unidade_id
        WHERE vi.condominio_id IS DISTINCT FROM u.condominio_id""",
    "visit_resident_tenant_mismatch": """SELECT COUNT(*) AS n FROM visitas vi
        JOIN moradores m ON m.id=vi.morador_id
        WHERE vi.condominio_id IS DISTINCT FROM m.condominio_id""",
    "parcel_unit_tenant_mismatch": """SELECT COUNT(*) AS n FROM encomendas e
        JOIN unidades u ON u.id=e.unidade_id
        WHERE e.condominio_id IS DISTINCT FROM u.condominio_id""",
    "lot_creator_tenant_mismatch": """SELECT COUNT(*) AS n FROM lotes_encomendas l
        JOIN usuarios u ON u.id=l.usuario_criacao_id
        WHERE l.condominio_id IS DISTINCT FROM u.condominio_id""",
    "invalid_foreign_keys": """SELECT COUNT(*) AS n FROM pg_constraint
        WHERE contype='f' AND NOT convalidated
          AND connamespace='public'::regnamespace""",
}


def main():
    if os.getenv("APP_ENV") not in ("test", "staging"):
        raise SystemExit("Preflight refused: APP_ENV must be test or staging")
    if os.getenv("ALLOW_ISOLATED_PREFLIGHT") != "yes":
        raise SystemExit("Preflight refused: set ALLOW_ISOLATED_PREFLIGHT=yes")
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Preflight refused: explicit isolated DATABASE_URL required")
    expected_database = os.getenv("EXPECTED_ISOLATED_DATABASE", "").strip()
    if not expected_database or expected_database in ("postgres", "portaria", "portaria_db"):
        raise SystemExit("Preflight refused: explicit non-production EXPECTED_ISOLATED_DATABASE required")
    conn = conectar_dedicado("portaria-isolated-release-preflight")
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() AS db")
            database = cur.fetchone()["db"]
            if database != expected_database:
                raise SystemExit("Preflight refused: connected database differs from expected isolated database")
            cur.execute("SELECT version, checksum FROM schema_migrations")
            recorded = {row["version"]: row["checksum"] for row in cur.fetchall()}
            migration_dir = Path(__file__).resolve().parents[1] / "migrations"
            expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in migration_dir.glob("[0-9]*.sql")}
            if len(expected) != 21 or recorded != expected:
                raise SystemExit("Preflight refused: migration versions/checksums differ from candidate source")
            failures = {}
            for name, statement in CHECKS.items():
                cur.execute(statement)
                count = cur.fetchone()["n"]
                print(f"{name}: {count}")
                if count:
                    failures[name] = count
            if failures:
                raise SystemExit(f"Release preflight failed: {failures}")
            print(f"Isolated database preflight passed: {database}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
