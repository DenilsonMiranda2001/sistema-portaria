from pathlib import Path
MIGRATION=Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
MONITOR=Path("hardware/monitor.py").read_text(encoding="utf-8")

def test_only_one_open_incident_exists_per_zone_and_type():
    assert "uq_hw_incident_open_zone_type" in MIGRATION
    assert "WHERE status = 'open'" in MIGRATION
    method=REPO.split("def reconcile_zone_incident",1)[1].split("def list_access_zone_operational_status",1)[0]
    assert "ON CONFLICT (condominio_id,access_zone_id,tipo) WHERE status='open'" in method

def test_incident_resolution_is_tenant_scoped():
    method=REPO.split("def reconcile_zone_incident",1)[1].split("def list_access_zone_operational_status",1)[0]
    assert "condominio_id=%s AND access_zone_id=%s::uuid" in method
    assert "status='resolved'" in method

def test_monitor_opens_for_unavailable_and_resolves_after_recovery():
    assert 'unavailable = zone["operational_status"] != "operational"' in MONITOR
    assert "reconcile_zone_incident(" in MONITOR
    assert "conn.commit()" in MONITOR
