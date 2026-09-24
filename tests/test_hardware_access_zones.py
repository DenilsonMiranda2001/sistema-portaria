from pathlib import Path
MIGRATION=Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
ROUTES=Path("routes/hardware_admin.py").read_text(encoding="utf-8")
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")

def test_access_zones_are_tenant_unique_and_scoped():
    assert "UNIQUE (condominio_id, codigo)" in MIGRATION
    assert "WHERE condominio_id=%s" in REPO.split("def list_access_zones",1)[1].split("def list_devices",1)[0]

def test_zone_admin_is_condominium_admin_only_and_audited():
    segment=ROUTES.split('@hardware_admin_bp.get("/zonas")',1)[1].split('@hardware_admin_bp.get("/permissoes")',1)[0]
    assert segment.count('@roles_required("admin_condominio")') == 3
    assert "hardware_access_zone_created" in segment
    assert "hardware_access_zone_deactivated" in segment
