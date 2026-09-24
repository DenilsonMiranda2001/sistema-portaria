from pathlib import Path
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
SERVICE=Path("hardware/service.py").read_text(encoding="utf-8")

def test_runtime_device_lookup_loads_relational_access_zone():
    method=REPO.split("def get_device(",1)[1].split("def list_credentials",1)[0]
    assert "access_zone_id::text" in method

def test_access_service_prefers_relational_zone_over_legacy_json():
    assert 'zone=device.get("access_zone_id") or (device.get("configuracao") or {}).get("zona")' in SERVICE
