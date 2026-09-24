from pathlib import Path


SOURCE = Path("hardware/worker.py").read_text(encoding="utf-8")


def test_worker_claims_and_commits_before_adapter_io():
    claim = SOURCE.split("def claim_command_batch", 1)[1].split("def finish_dispatched_command", 1)[0]
    dispatch = SOURCE.split("def dispatch_claimed_commands", 1)[1]
    assert "conn.commit()" in claim
    assert "adapter.send_command(command)" in dispatch
    assert "conn =" not in dispatch


def test_each_command_result_uses_short_separate_transaction():
    finish = SOURCE.split("def finish_dispatched_command", 1)[1].split("def _load_device", 1)[0]
    assert "conectar()" in finish
    assert ".finish_command(" in finish
    assert "conn.commit()" in finish
    assert "liberar(conn)" in finish


def test_adapter_error_details_are_not_persisted_verbatim():
    dispatch = SOURCE.split("def dispatch_claimed_commands", 1)[1]
    assert "result.detail" not in dispatch
    assert 'error=None if result.accepted else "adapter_rejected"' in dispatch
    assert "type(exc).__name__" in dispatch
    assert "logger.exception" not in dispatch
