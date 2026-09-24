from pathlib import Path


def test_provisioning_generates_secret_but_persists_only_verifier():
    source = Path("hardware/provisioning.py").read_text(encoding="utf-8")
    repo = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(32)" in source
    assert "secret_verifier(secret)" in source
    assert "auth_secret_hash" in repo
    assert "auth_secret VARCHAR" not in Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")


def test_rotation_and_revocation_are_tenant_scoped():
    repo = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "def rotate_device_secret" in repo
    assert "def revoke_device_auth" in repo
    assert repo.count("WHERE condominio_id=%s AND id=%s::uuid") >= 2


def test_physical_device_is_not_provisioned_by_simulator_service():
    source = Path("hardware/provisioning.py").read_text(encoding="utf-8")
    assert 'vendor="simulator"' in source
