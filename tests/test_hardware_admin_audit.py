from pathlib import Path


ROUTES = Path("routes/hardware_admin.py").read_text(encoding="utf-8")


def test_sensitive_hardware_admin_actions_are_audited():
    assert "hardware_device_provisioned" in ROUTES
    assert "hardware_device_secret_rotated" in ROUTES
    assert "hardware_device_auth_revoked" in ROUTES
    assert ROUTES.count("registrar_auditoria_cursor") >= 4


def test_audit_details_never_include_plaintext_secret():
    audit_calls = [line for line in ROUTES.splitlines() if "registrar_auditoria_cursor" in line or '{"vendor"' in line]
    assert all('"secret"' not in line and '"segredo"' not in line for line in audit_calls)
