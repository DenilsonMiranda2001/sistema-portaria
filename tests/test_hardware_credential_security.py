import pytest
from hardware.access import credential_fingerprint


def test_fingerprint_is_stable_with_same_key_and_changes_with_different_key():
    a = credential_fingerprint("TAG-001", key=b"a" * 32)
    b = credential_fingerprint("TAG-001", key=b"a" * 32)
    c = credential_fingerprint("TAG-001", key=b"b" * 32)
    assert a == b
    assert a != c
    assert "TAG-001" not in a


def test_short_hmac_key_is_rejected():
    with pytest.raises(RuntimeError):
        credential_fingerprint("TAG-001", key=b"short")


def test_production_has_no_implicit_credential_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("HARDWARE_CREDENTIAL_HMAC_KEY", raising=False)
    with pytest.raises(RuntimeError):
        credential_fingerprint("TAG-001")
