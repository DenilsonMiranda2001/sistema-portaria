from pathlib import Path


def test_cross_table_login_identity_is_serialized_in_database():
    sql = Path("migrations/0010_cross_table_login_identity.sql").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in sql
    assert "platform_admins" in sql
    assert "usuarios" in sql
    assert "BEFORE INSERT OR UPDATE OF usuario" in sql
    assert "23505" in sql
