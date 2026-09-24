from pathlib import Path


def test_device_secret_is_not_selected_from_database():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "auth_secret_hash" in source
    assert "auth_secret," not in source
    assert "auth_secret VARCHAR" not in Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")


def test_auth_requires_stored_verifier_not_persisted_plaintext():
    source = Path("hardware/auth.py").read_text(encoding="utf-8")
    assert "stored_verifier = device.get(\"auth_secret_hash\")" in source
    assert "hmac.compare_digest(secret_verifier(secret), stored_verifier)" in source
