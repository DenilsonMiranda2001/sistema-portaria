from pathlib import Path


ROUTES = Path("routes/hardware_admin.py").read_text(encoding="utf-8")
REPO = Path("hardware/repository.py").read_text(encoding="utf-8")


def test_policy_admin_routes_require_condominium_admin():
    segment = ROUTES.split('@hardware_admin_bp.get("/permissoes")', 1)[1].split('@hardware_admin_bp.post("/<uuid:device_id>/zona")', 1)[0]
    assert segment.count('@roles_required("admin_condominio")') == 3


def test_policy_creation_requires_active_same_tenant_credential_and_zone():
    method = REPO.split("def create_access_policy", 1)[1].split("def deactivate_access_policy", 1)[0]
    assert "z.condominio_id=%s AND z.ativo" in method
    assert "c.condominio_id=%s AND c.ativo" in method


def test_policy_route_rejects_empty_or_invalid_weekdays_and_partial_time_window():
    segment = ROUTES.split("def criar_permissao", 1)[1].split("def desativar_permissao", 1)[0]
    assert "not weekdays" in segment
    assert "day < 0 or day > 6" in segment
    assert "bool(start_time) != bool(end_time)" in segment


def test_policy_changes_are_audited_without_raw_credentials():
    segment = ROUTES.split('@hardware_admin_bp.get("/permissoes")', 1)[1].split('@hardware_admin_bp.post("/simulador")', 1)[0]
    assert "hardware_access_policy_created" in segment
    assert "hardware_access_policy_deactivated" in segment
    assert "raw_identifier" not in segment

def test_policy_route_validates_uuid_and_time_before_database():
    segment = ROUTES.split("def criar_permissao", 1)[1].split("def desativar_permissao", 1)[0]
    assert "uuid.UUID(credential_id)" in segment
    assert "uuid.UUID(access_zone_id)" in segment
    assert "time.fromisoformat(start_time)" in segment

def test_policy_repository_names_logical_zone_explicitly():
    method = REPO.split("def create_access_policy", 1)[1].split("def deactivate_access_policy", 1)[0]
    assert "access_zone_id" in method.split("weekdays", 1)[0]
