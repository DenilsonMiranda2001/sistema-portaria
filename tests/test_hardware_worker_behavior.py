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
