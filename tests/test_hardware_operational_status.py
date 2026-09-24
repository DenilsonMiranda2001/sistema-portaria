from pathlib import Path
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
ROUTES=Path("routes/hardware_admin.py").read_text(encoding="utf-8")

def test_operational_status_is_tenant_scoped_and_fail_safe():
    method=REPO.split("def list_device_operational_status",1)[1].split("def list_devices",1)[0]
    assert "WHERE d.condominio_id=%s" in method
    for state in ["inactive","auth_revoked","unassigned","never_seen","offline","online"]:
        assert "'"+state+"'" in method
    assert "ultimo_heartbeat_em < CURRENT_TIMESTAMP" in method

def test_admin_surfaces_every_non_online_device_as_alert():
    segment=ROUTES.split("def dispositivos",1)[1].split('@hardware_admin_bp.get("/credenciais")',1)[0]
    assert 'd["operational_status"] != "online"' in segment
