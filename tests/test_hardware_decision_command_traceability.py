from pathlib import Path
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
SERVICE=Path("hardware/service.py").read_text(encoding="utf-8")
MIGRATION=Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")

def test_decision_id_is_persisted_on_command():
    assert "RETURNING id" in REPO.split("def record_access_decision",1)[1].split("def device_is_online",1)[0]
    assert "decision_id=decision_id" in SERVICE
    enqueue=REPO.split("def enqueue_command",1)[1].split("def mark_heartbeat",1)[0]
    assert "decision_id" in enqueue

def test_dispatch_revalidation_uses_exact_decision():
    method=REPO.split("def access_command_still_authorized",1)[1].split("def finish_command",1)[0]
    assert "dec.id=cmd.decision_id" in method

def test_database_enforces_tenant_safe_decision_link():
    assert "uq_hw_decision_id_tenant" in MIGRATION
    assert "fk_hw_commands_decision_tenant" in MIGRATION
    assert "FOREIGN KEY (decision_id, condominio_id)" in MIGRATION
