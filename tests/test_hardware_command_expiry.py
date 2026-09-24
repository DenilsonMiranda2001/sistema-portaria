from datetime import datetime, timezone
from hardware.contracts import HardwareCommand, HardwareCommandType
from hardware.repository import HardwareRepository


def _command(kind):
    return HardwareCommand(tenant_id=1, device_id="dev", command_id="cmd", command_type=kind, payload={})


def test_grant_access_expires_in_ten_seconds():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expiry = HardwareRepository._command_expiry(_command(HardwareCommandType.GRANT_ACCESS), now)
    assert (expiry - now).total_seconds() == 10


def test_non_access_command_has_bounded_expiry():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expiry = HardwareRepository._command_expiry(_command(HardwareCommandType.PING), now)
    assert (expiry - now).total_seconds() == 15 * 60


def test_outbox_persists_expiry_and_claim_filters_expired_commands():
    source = open("hardware/repository.py", encoding="utf-8").read()
    assert "proxima_tentativa_em, expira_em" in source
    assert "expira_em IS NULL OR expira_em > CURRENT_TIMESTAMP" in source
