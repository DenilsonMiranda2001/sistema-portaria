import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DeviceAuthResult:
    authenticated: bool
    reason: str
    device: dict | None = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_message(*, key_id: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()
    return f"{key_id}\n{timestamp}\n{nonce}\n{body_hash}".encode("utf-8")


def verify_device_request(
    *,
    key_id: str,
    timestamp: str,
    nonce: str,
    signature: str,
    body: bytes,
    device_lookup: Callable,
    nonce_consume: Callable,
    now: int | None = None,
    max_clock_skew_seconds: int = 60,
) -> DeviceAuthResult:
    """Authenticate machine requests and fail closed on stale/replayed messages."""
    device = device_lookup(key_id)
    if not device or not device.get("ativo") or device.get("auth_revoked_em"):
        return DeviceAuthResult(False, "device_auth_unavailable")
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return DeviceAuthResult(False, "invalid_timestamp")
    current = int(time.time() if now is None else now)
    if abs(current - sent_at) > max_clock_skew_seconds:
        return DeviceAuthResult(False, "stale_request")
    if not nonce or len(nonce) < 16:
        return DeviceAuthResult(False, "invalid_nonce")
    secret = device.get("auth_secret")
    if not secret:
        return DeviceAuthResult(False, "device_secret_unavailable")
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical_message(key_id=key_id, timestamp=timestamp, nonce=nonce, body=body),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        return DeviceAuthResult(False, "invalid_signature")
    if not nonce_consume(device["id"], _digest(nonce), current + max_clock_skew_seconds):
        return DeviceAuthResult(False, "replayed_request")
    return DeviceAuthResult(True, "authenticated", device)
