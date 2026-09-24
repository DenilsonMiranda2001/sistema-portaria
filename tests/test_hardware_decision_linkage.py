from pathlib import Path


REPOSITORY = Path("hardware/repository.py").read_text(encoding="utf-8")
MIGRATION = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")


def test_persisted_event_returns_internal_database_id():
    persist = REPOSITORY.split("def persist_event", 1)[1].split("def enqueue_command", 1)[0]
    assert "RETURNING id" in persist
    assert 'return row["id"] if row else None' in persist


def test_access_decision_requires_and_persists_internal_event_link():
    decision = REPOSITORY.split("def record_access_decision", 1)[1].split("def device_is_online", 1)[0]
    assert "hardware_event_missing_for_decision" in decision
    assert "(condominio_id, device_id, event_id, external_event_id" in decision


def test_event_decision_foreign_key_is_tenant_scoped():
    assert "FOREIGN KEY (event_id, condominio_id)" in MIGRATION
    assert "REFERENCES hardware_events(id, condominio_id)" in MIGRATION
