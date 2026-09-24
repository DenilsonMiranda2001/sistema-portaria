import pytest

from hardware.monitor import reconcile_hardware_incidents


@pytest.mark.parametrize("tenant_id", [None, 0, -1, True, "7"])
def test_monitor_rejects_invalid_tenant_before_database_access(tenant_id):
    with pytest.raises(ValueError, match="tenant_id must be a positive integer"):
        reconcile_hardware_incidents(tenant_id)


@pytest.mark.parametrize("stale_seconds", [None, 0, -1, True, 1.5, "90"])
def test_monitor_rejects_invalid_stale_window_before_database_access(stale_seconds):
    with pytest.raises(ValueError, match="stale_seconds must be a positive integer"):
        reconcile_hardware_incidents(7, stale_seconds=stale_seconds)
