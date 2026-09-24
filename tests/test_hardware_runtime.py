from pathlib import Path
RUNTIME=Path("hardware/runtime.py").read_text(encoding="utf-8")
PROCFILE=Path("Procfile").read_text(encoding="utf-8")

def test_runtime_uses_postgres_leader_election_for_monitor():
    assert "pg_try_advisory_lock" in RUNTIME
    assert "pg_advisory_unlock" in RUNTIME
    assert "monitor_leader" in RUNTIME

def test_command_dispatch_can_scale_without_global_worker_lock():
    assert "dispatch_claimed_commands(registry)" in RUNTIME
    # Command claims themselves use FOR UPDATE SKIP LOCKED in the repository.

def test_runtime_handles_termination_and_has_separate_process():
    assert "SIGTERM" in RUNTIME
    assert "SIGINT" in RUNTIME
    assert "hardware-worker: python -m hardware.runtime" in PROCFILE

def test_simulator_adapter_is_opt_in():
    assert 'HARDWARE_SIMULATOR_HTTP_ENABLED' in RUNTIME

def test_runtime_retries_failed_cycles_without_logging_sensitive_exception_text():
    assert "consecutive_failures += 1" in RUNTIME
    assert "min(30," in RUNTIME
    assert "type(exc).__name__" in RUNTIME
    assert "str(exc)" not in RUNTIME

def test_monitor_leadership_can_be_reacquired():
    assert "def _acquire_monitor_leader" in RUNTIME
    assert "if leader is None:" in RUNTIME

def test_worker_health_probe_is_database_backed():
    health=Path("hardware/health.py").read_text(encoding="utf-8")
    assert "SELECT 1 AS ok" in health
    assert "SystemExit(0 if database_ready() else 1)" in health


def test_monitor_leadership_connection_is_health_checked_and_reacquired():
    assert "def _leader_connection_alive" in SOURCE
    assert 'cur.execute("SELECT 1 AS ok")' in SOURCE
    assert "leader is not None and not _leader_connection_alive(leader)" in SOURCE
    assert 'logger.warning("hardware monitor leadership connection lost")' in SOURCE
