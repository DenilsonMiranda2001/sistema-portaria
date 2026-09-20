from pathlib import Path


def test_platform_routes_have_no_raw_cursor_sql():
    source = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    assert "cur.execute(" not in source
    assert "conectar()" not in source


def test_visit_workflows_validate_actor_and_resident_unit():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert "Usuário de entrada inválido para este condomínio." in source
    assert "Usuário de saída inválido para este condomínio." in source
    assert "O morador selecionado não pertence à unidade informada." in source


def test_resident_atomic_workflows_reject_inactive_unit_reuse():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert source.count("Esta unidade existe, mas está inativa.") >= 2


def test_visitor_profile_address_is_separate_from_visit_destination():
    models = Path("database/models.py").read_text(encoding="utf-8")
    migration = Path("migrations/0011_visitor_profile_address.sql").read_text(encoding="utf-8")
    routes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS endereco TEXT" in migration
    assert "endereco=None, entrada=None" in models
    assert 'endereco=endereco' in routes
    assert '"endereco": ""' in routes


def test_central_package_reception_is_default():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert "'retida_portaria'" in source
    assert "retirada" in source


def test_noop_locked_mutations_close_transactions():
    models = Path("database/models.py").read_text(encoding="utf-8")
    platform = Path("database/platform.py").read_text(encoding="utf-8")
    packages = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert 'conn.rollback()\n                return False' in models
    assert platform.count('conn.rollback()\n                    return False') >= 1
    assert 'conn.rollback()\n                return False' in packages


def test_audit_ip_hash_is_safe_without_request_context():
    audit = Path("utils/audit.py").read_text(encoding="utf-8")
    assert "has_request_context" in audit
    assert "if not has_request_context()" in audit


def test_login_identity_invariant_migration_exists():
    migration = Path("migrations/0012_login_identity_invariant.sql").read_text(encoding="utf-8")
    assert "JOIN platform_admins" in migration
    assert "duplicate tenant login" in migration


def test_open_visit_uniqueness_is_enforced_at_database_level():
    migration = Path("migrations/0013_operational_integrity_indexes.sql").read_text(encoding="utf-8")
    assert "HAVING COUNT(*) > 1" in migration
    assert "uq_visita_aberta_visitante_tenant" in migration
    assert "WHERE data_saida IS NULL" in migration


def test_hot_operational_queries_have_tenant_scoped_indexes():
    migration = Path("migrations/0013_operational_integrity_indexes.sql").read_text(encoding="utf-8")
    assert "idx_visitas_tenant_abertas" in migration
    assert "idx_encomendas_tenant_custodia" in migration
    assert "idx_moradores_tenant_ativos_unidade" in migration
