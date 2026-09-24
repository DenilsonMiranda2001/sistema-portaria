from pathlib import Path


def test_device_auth_is_signed_and_fail_closed():
    source = Path("hardware/auth.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in source
    assert "stale_request" in source
    assert "invalid_signature" in source


def test_device_auth_has_replay_protection():
    source = Path("hardware/auth.py").read_text(encoding="utf-8")
    assert "nonce_consume" in source
    assert "replayed_request" in source


def test_auth_schema_supports_rotation_and_revocation():
    sql = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "auth_secret_rotated_em" in sql
    assert "auth_revoked_em" in sql
    assert "hardware_auth_nonces" in sql
