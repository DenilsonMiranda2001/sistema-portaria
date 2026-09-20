from pathlib import Path


def test_platform_mutations_own_their_audit_transaction():
    data = Path("database/platform.py").read_text(encoding="utf-8")
    routes = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    assert "registrar_auditoria_cursor" in data
    for event in ("plataforma.condominio_criado", "plataforma.usuario_tenant_criado", "plataforma.condominio_atualizado", "plataforma.condominio_status", "plataforma.usuario_tenant_status"):
        assert event in data
        assert event not in routes
    assert "registrar_auditoria(" not in routes
