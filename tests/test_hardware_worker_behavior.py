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
