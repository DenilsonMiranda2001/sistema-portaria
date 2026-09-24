from pathlib import Path


SQL = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")


def test_hardware_device_and_credential_have_composite_tenant_identity():
    assert "UNIQUE (id, condominio_id)" in SQL
    assert "uq_hw_moradores_id_tenant" in SQL
    assert "uq_hw_visitantes_id_tenant" in SQL
    assert "REFERENCES moradores(id, condominio_id)" in SQL
    assert "REFERENCES visitantes(id, condominio_id)" in SQL


def test_event_command_policy_and_decision_are_tenant_bound():
    assert SQL.count("REFERENCES hardware_devices(id, condominio_id)") >= 4
    assert "REFERENCES hardware_credentials(id, condominio_id)" in SQL
    assert "REFERENCES hardware_events(id, condominio_id)" in SQL


def test_credential_cannot_be_ambiguously_linked_to_resident_and_visitor():
    assert "CHECK (NOT (morador_id IS NOT NULL AND visitante_id IS NOT NULL))" in SQL
