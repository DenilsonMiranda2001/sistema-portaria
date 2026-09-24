from pathlib import Path


def test_hardware_schema_and_outbox_contracts_exist():
    sql = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "UNIQUE (condominio_id, device_id, external_event_id)" in sql
    assert "hardware_commands" in sql
    assert "processing" in sql


def test_repository_claims_commands_concurrently_without_double_claim():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "status='processing'" in source
    assert "ON CONFLICT (condominio_id, device_id, external_event_id) DO NOTHING" in source


def test_access_service_uses_transactional_outbox_without_device_io():
    source = Path("hardware/service.py").read_text(encoding="utf-8")
    assert "repo.enqueue_command" in source
    assert ".send_command(" not in source
    assert "conn.rollback()" in source
