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
