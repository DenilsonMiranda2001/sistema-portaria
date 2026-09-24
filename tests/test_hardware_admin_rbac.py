from pathlib import Path


ROUTES = Path("routes/hardware_admin.py").read_text(encoding="utf-8")


def test_every_hardware_admin_action_requires_condominium_admin():
    assert ROUTES.count('@roles_required("admin_condominio")') == 4


def test_hardware_admin_operations_use_authenticated_tenant():
    assert ROUTES.count("tenant_id=g.tenant_id") >= 3
    assert "session.get(" not in ROUTES
    assert "request.form.get("condominio" not in ROUTES


def test_only_simulator_can_be_created_from_admin_ui():
    assert "provision_simulator_device" in ROUTES
    assert "ControlID" not in ROUTES
