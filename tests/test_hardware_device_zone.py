from pathlib import Path
MIGRATION=Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
ROUTES=Path("routes/hardware_admin.py").read_text(encoding="utf-8")

def test_device_zone_fk_is_tenant_scoped():
    assert "FOREIGN KEY (access_zone_id, condominio_id)" in MIGRATION
    assert "REFERENCES hardware_access_zones(id, condominio_id)" in MIGRATION

def test_zone_assignment_requires_same_tenant_and_active_zone():
    method=REPO.split("def assign_device_zone",1)[1].split("def create_device_identity",1)[0]
    assert "d.condominio_id=%s" in method
    assert "z.condominio_id=d.condominio_id" in method
    assert "z.ativo" in method

def test_zone_assignment_is_admin_only_and_audited():
    segment=ROUTES.split("def vincular_zona_dispositivo",1)[1].split('@hardware_admin_bp.post("/simulador")',1)[0]
    prefix=ROUTES[:ROUTES.index("def vincular_zona_dispositivo")]
    assert '@roles_required("admin_condominio")' in prefix[-120:]
    assert "hardware_device_zone_assigned" in segment
