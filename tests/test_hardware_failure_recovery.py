from pathlib import Path


def test_command_retry_ceiling_and_decision_audit_are_in_schema():
    sql = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "max_tentativas INTEGER NOT NULL DEFAULT 5" in sql
    assert "hardware_access_decisions" in sql
    assert "credential_hash VARCHAR(64)" in sql


def test_stuck_processing_commands_are_recoverable():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "def recover_stuck_commands" in source
    assert "processing_timeout" in source
    assert "tentativas >= max_tentativas" in source


def test_access_decision_is_persisted_before_commit():
    source = Path("hardware/service.py").read_text(encoding="utf-8")
    decision_pos = source.index("repo.record_access_decision")
    commit_pos = source.index("conn.commit()", decision_pos)
    assert decision_pos < commit_pos


def test_device_liveness_comes_from_heartbeat_not_process_memory():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "def device_is_online" in source
    assert "ultimo_heartbeat_em >=" in source
