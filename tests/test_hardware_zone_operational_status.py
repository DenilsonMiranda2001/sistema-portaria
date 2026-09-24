from pathlib import Path
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
ROUTES=Path("routes/hardware_admin.py").read_text(encoding="utf-8")

def test_zone_health_requires_at_least_one_online_non_revoked_device():
    method=REPO.split("def list_access_zone_operational_status",1)[1].split("def list_access_zones",1)[0]
    assert "d.auth_revoked_em IS NULL" in method
    assert "d.ultimo_heartbeat_em >= CURRENT_TIMESTAMP" in method
    assert "'no_device'" in method
    assert "'unavailable'" in method
    assert "'operational'" in method

def test_zone_health_is_strictly_tenant_scoped():
    method=REPO.split("def list_access_zone_operational_status",1)[1].split("def list_access_zones",1)[0]
    assert "d.condominio_id=z.condominio_id" in method
    assert "WHERE z.condominio_id=%s" in method

def test_admin_alerts_only_active_non_operational_zones():
    segment=ROUTES.split("def zonas",1)[1].split("def criar_zona",1)[0]
    assert 'z["ativo"] and z["operational_status"] != "operational"' in segment
