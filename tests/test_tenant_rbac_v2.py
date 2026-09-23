from pathlib import Path


def test_tenant_rbac_migration_is_explicit_and_forward_only():
    sql = Path("migrations/0020_tenant_rbac_roles.sql").read_text(encoding="utf-8")
    assert "admin_condominio" in sql
    assert "administrativo" in sql
    assert "porteiro" in sql
    assert "UPDATE usuarios SET nivel = 'admin_condominio' WHERE nivel = 'admin'" in sql
    assert "UPDATE usuarios SET nivel = 'porteiro' WHERE nivel = 'funcionario'" in sql


def test_authz_canonicalizes_legacy_roles_during_rolling_deploy():
    source = Path("utils/authz.py").read_text(encoding="utf-8")
    assert '"admin": "admin_condominio"' in source
    assert '"funcionario": "porteiro"' in source
    assert "canonical_role" in source


def test_tenant_admin_is_only_role_that_manages_users():
    source = Path("routes/admin.py").read_text(encoding="utf-8")
    assert source.count('@roles_required("admin_condominio")') >= 6
    assert '"administrativo"' in source
    assert '"porteiro"' in source


def test_operational_roles_are_explicit():
    expected = '@roles_required("admin_condominio", "administrativo", "porteiro")'
    for path in ("routes/moradores.py", "routes/visitantes.py", "routes/encomendas.py", "routes/entregadores.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert expected in source
