from pathlib import Path


def test_tenant_integrity_migration_covers_critical_relations():
    sql = Path("migrations/0005_tenant_relational_integrity.sql").read_text(encoding="utf-8")
    expected = [
        "fk_moradores_unidade_tenant",
        "fk_visitas_visitante_tenant",
        "fk_visitas_unidade_tenant",
        "fk_visitas_morador_tenant",
        "fk_visitas_usuario_entrada_tenant",
        "fk_visitas_usuario_saida_tenant",
        "fk_lotes_usuario_tenant",
        "fk_encomendas_lote_tenant",
        "fk_encomendas_morador_tenant",
        "fk_encomendas_unidade_tenant",
        "fk_encomendas_usuario_tenant",
    ]
    for constraint in expected:
        assert constraint in sql
    assert sql.count("condominio_id)") >= len(expected)


def test_audit_schema_supports_non_tenant_platform_actor():
    sql = Path("migrations/0006_audit_actor_identity.sql").read_text(encoding="utf-8")
    assert "actor_tipo" in sql
    assert "actor_id" in sql
    assert "idx_audit_actor_time" in sql


def test_legacy_sqlite_database_module_is_removed():
    assert not Path("database/database.py").exists()


def test_package_constraints_are_eventually_validated():
    migration = Path("migrations/0016_validate_package_constraints.sql").read_text(encoding="utf-8")
    assert "VALIDATE CONSTRAINT ck_encomendas_status_known" in migration
    assert "VALIDATE CONSTRAINT ck_encomendas_retirada_evidence" in migration


def test_request_telemetry_keeps_request_id_status_and_duration():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f" in source
    assert "time.perf_counter()" in source


def test_visit_indexes_avoid_duplicate_open_visit_barriers():
    migration = Path("migrations/0017_visit_index_cleanup.sql").read_text(encoding="utf-8")
    assert "DROP INDEX IF EXISTS uq_visitas_tenant_visitante_ativa" in migration
    assert "idx_visitas_tenant_saida" in migration
