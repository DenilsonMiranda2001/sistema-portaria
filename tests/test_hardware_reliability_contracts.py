from pathlib import Path


def test_hardware_commands_have_explicit_expiry_and_completion():
    sql = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "expira_em TIMESTAMPTZ" in sql
    assert "concluido_em TIMESTAMPTZ" in sql


def test_worker_uses_bounded_backoff_and_expires_stale_commands():
    source = Path("hardware/worker.py").read_text(encoding="utf-8")
    assert "repo.expire_commands()" in source
    assert "min(300, 5 * (2 **" in source


def test_repository_supports_device_heartbeat():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "def mark_heartbeat" in source
    assert "ultimo_heartbeat_em=CURRENT_TIMESTAMP" in source
