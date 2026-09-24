from types import SimpleNamespace
from unittest.mock import Mock, patch

from hardware.contracts import HardwareCommandType
from hardware.worker import dispatch_claimed_commands


def _grant_row():
    return {
        "id": "command-1",
        "condominio_id": 7,
        "device_id": "device-1",
        "tipo": HardwareCommandType.GRANT_ACCESS.value,
        "payload": {"source_event_id": "event-1"},
        "tentativas": 1,
    }


def test_revoked_device_never_reaches_adapter_io_and_grant_is_terminal():
    registry = Mock()
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": "2026-09-24T13:00:00Z",
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized") as revalidate, \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    registry.get.assert_not_called()
    revalidate.assert_not_called()
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="RuntimeError",
        retry_seconds=5, retryable=False,
    )


def test_revoked_device_non_access_command_remains_retryable_without_io():
    row = _grant_row()
    row["tipo"] = HardwareCommandType.PING.value
    registry = Mock()
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[row]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": "2026-09-24T13:00:00Z",
             "vendor": "simulator",
         }), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    registry.get.assert_not_called()
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="RuntimeError",
        retry_seconds=5, retryable=True,
    )



def test_grant_revoked_by_revalidation_is_terminal_without_adapter_io():
    registry = Mock()
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=False) as revalidate, \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    revalidate.assert_called_once_with(7, "command-1", "device-1")
    registry.get.assert_not_called()
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="authorization_revoked",
        retry_seconds=300, retryable=False,
    )


def test_authorized_grant_reaches_adapter_and_records_success():
    row = _grant_row()
    adapter = Mock()
    adapter.send_command.return_value = SimpleNamespace(accepted=True, safe_to_retry=False)
    registry = Mock()
    registry.get.return_value = adapter
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[row]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=True), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 1}
    registry.get.assert_called_once_with("simulator")
    adapter.send_command.assert_called_once()
    command = adapter.send_command.call_args.args[0]
    assert command.tenant_id == 7
    assert command.device_id == "device-1"
    assert command.command_id == "command-1"
    assert command.command_type is HardwareCommandType.GRANT_ACCESS
    assert command.payload == {"source_event_id": "event-1"}
    finish.assert_called_once_with(
        "command-1", succeeded=True, error=None,
        retry_seconds=5, retryable=True,
    )



def test_rejected_grant_is_terminal_without_explicit_safe_retry():
    adapter = Mock()
    adapter.send_command.return_value = SimpleNamespace(accepted=False, safe_to_retry=False)
    registry = Mock()
    registry.get.return_value = adapter
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=True), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    adapter.send_command.assert_called_once()
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="adapter_rejected",
        retry_seconds=5, retryable=False,
    )


def test_rejected_grant_retries_only_when_adapter_explicitly_marks_safe():
    adapter = Mock()
    adapter.send_command.return_value = SimpleNamespace(accepted=False, safe_to_retry=True)
    registry = Mock()
    registry.get.return_value = adapter
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=True), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="adapter_rejected",
        retry_seconds=5, retryable=True,
    )


def test_ambiguous_grant_adapter_exception_is_terminal():
    adapter = Mock()
    adapter.send_command.side_effect = TimeoutError("ambiguous acknowledgement")
    registry = Mock()
    registry.get.return_value = adapter
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "simulator",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=True), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="TimeoutError",
        retry_seconds=5, retryable=False,
    )



def test_retry_backoff_is_capped_at_five_minutes():
    row = _grant_row()
    row["tipo"] = HardwareCommandType.PING.value
    row["tentativas"] = 20
    registry = Mock()
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[row]), \
         patch("hardware.worker._load_device", return_value=None), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    registry.get.assert_not_called()
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="RuntimeError",
        retry_seconds=300, retryable=True,
    )


def test_retry_backoff_uses_attempt_count_before_cap():
    expected = ((1, 5), (2, 10), (3, 20), (4, 40))
    for attempts, retry_seconds in expected:
        row = _grant_row()
        row["tipo"] = HardwareCommandType.PING.value
        row["tentativas"] = attempts
        finish = Mock()
        with patch("hardware.worker.claim_command_batch", return_value=[row]), \
             patch("hardware.worker._load_device", return_value=None), \
             patch("hardware.worker.finish_dispatched_command", finish):
            dispatch_claimed_commands(Mock())
        finish.assert_called_once_with(
            "command-1", succeeded=False, error="RuntimeError",
            retry_seconds=retry_seconds, retryable=True,
        )



def test_unknown_vendor_never_attempts_device_io_and_grant_is_terminal():
    registry = Mock()
    registry.get.side_effect = LookupError("unsupported hardware vendor")
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[_grant_row()]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "unknown-vendor",
         }), \
         patch("hardware.worker._access_command_still_authorized", return_value=True), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    registry.get.assert_called_once_with("unknown-vendor")
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="LookupError",
        retry_seconds=5, retryable=False,
    )


def test_unknown_vendor_non_access_command_is_retryable():
    row = _grant_row()
    row["tipo"] = HardwareCommandType.PING.value
    registry = Mock()
    registry.get.side_effect = LookupError("unsupported hardware vendor")
    finish = Mock()
    with patch("hardware.worker.claim_command_batch", return_value=[row]), \
         patch("hardware.worker._load_device", return_value={
             "id": "device-1", "ativo": True, "auth_revoked_em": None,
             "vendor": "unknown-vendor",
         }), \
         patch("hardware.worker.finish_dispatched_command", finish):
        result = dispatch_claimed_commands(registry)

    assert result == {"claimed": 1, "succeeded": 0}
    finish.assert_called_once_with(
        "command-1", succeeded=False, error="LookupError",
        retry_seconds=5, retryable=True,
    )
