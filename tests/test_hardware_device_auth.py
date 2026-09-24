import hashlib
import hmac

from hardware.auth import canonical_message, secret_verifier, verify_device_request


DEVICE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "condominio_id": 7,
    "ativo": True,
    "auth_revoked_em": None,
    "auth_secret_hash": secret_verifier("device-secret"),
    "_presented_secret": "device-secret",
}


def _signature(timestamp="1000", nonce="1234567890abcdef", body=b'{}'):
    return hmac.new(
        b"device-secret",
        canonical_message(key_id="hw_key", timestamp=timestamp, nonce=nonce, body=body),
        hashlib.sha256,
    ).hexdigest()


def _verify(**overrides):
    args = {
        "key_id": "hw_key",
        "timestamp": "1000",
        "nonce": "1234567890abcdef",
        "signature": _signature(),
        "body": b"{}",
        "device_lookup": lambda key_id: dict(DEVICE),
        "nonce_consume": lambda device_id, nonce_hash, expires_at: True,
        "now": 1000,
    }
    args.update(overrides)
    return verify_device_request(**args)


def test_valid_device_request_authenticates():
    result = _verify()
    assert result.authenticated is True
    assert result.reason == "authenticated"
    assert result.device["condominio_id"] == 7


def test_unknown_inactive_and_revoked_devices_fail_closed():
    unknown = _verify(device_lookup=lambda key_id: None)
    inactive = _verify(device_lookup=lambda key_id: {**DEVICE, "ativo": False})
    revoked = _verify(device_lookup=lambda key_id: {**DEVICE, "auth_revoked_em": "2026-09-24T00:00:00Z"})
    assert unknown.reason == "device_auth_unavailable"
    assert inactive.reason == "device_auth_unavailable"
    assert revoked.reason == "device_auth_unavailable"


def test_invalid_timestamp_and_clock_skew_fail_closed():
    invalid = _verify(timestamp="not-a-number")
    stale = _verify(timestamp="900")
    future = _verify(timestamp="1100")
    assert invalid.reason == "invalid_timestamp"
    assert stale.reason == "stale_request"
    assert future.reason == "stale_request"


def test_nonce_must_be_long_enough():
    result = _verify(nonce="short")
    assert result.reason == "invalid_nonce"


def test_secret_and_signature_are_verified():
    wrong_secret_device = {**DEVICE, "_presented_secret": "wrong"}
    wrong_secret = _verify(device_lookup=lambda key_id: wrong_secret_device)
    wrong_signature = _verify(signature="0" * 64)
    assert wrong_secret.reason == "invalid_secret"
    assert wrong_signature.reason == "invalid_signature"


def test_nonce_is_consumed_only_after_cryptographic_authentication():
    calls = []
    result = _verify(nonce_consume=lambda device_id, nonce_hash, expires_at: calls.append(
        (device_id, nonce_hash, expires_at)
    ) or True)
    assert result.authenticated is True
    assert len(calls) == 1
    device_id, nonce_hash, expires_at = calls[0]
    assert device_id == DEVICE["id"]
    assert nonce_hash == hashlib.sha256(b"1234567890abcdef").hexdigest()
    assert expires_at == 1060


def test_replayed_nonce_fails_closed():
    result = _verify(nonce_consume=lambda device_id, nonce_hash, expires_at: False)
    assert result.authenticated is False
    assert result.reason == "replayed_request"


def test_body_is_covered_by_signature():
    result = _verify(body=b'{"changed":true}')
    assert result.authenticated is False
    assert result.reason == "invalid_signature"


def test_auth_schema_supports_rotation_and_revocation():
    from pathlib import Path

    sql = Path("migrations/0022_hardware_integration_foundation.sql").read_text(encoding="utf-8")
    assert "auth_secret_rotated_em" in sql
    assert "auth_revoked_em" in sql
    assert "hardware_auth_nonces" in sql
