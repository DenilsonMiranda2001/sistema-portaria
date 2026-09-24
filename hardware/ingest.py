from datetime import datetime, timedelta, timezone
from .contracts import HardwareEvent, HardwareEventType


ALLOWED_EVENT_KEYS = {"event_id", "event_type", "occurred_at", "credential", "payload"}
ALLOWED_PAYLOAD_KEYS = {"reader", "direction", "door", "zone", "signal", "source"}
MAX_EVENT_AGE = timedelta(minutes=5)
MAX_EVENT_FUTURE_SKEW = timedelta(minutes=1)


class InvalidHardwareEvent(ValueError):
    pass


def build_authenticated_event(device: dict, data: dict) -> HardwareEvent:
    """Build an event only from an authenticated device identity.

    Tenant and device identifiers supplied by callers are deliberately ignored.
    """
    if not isinstance(data, dict):
        raise InvalidHardwareEvent("invalid_json")
    unknown_event_keys = set(data) - ALLOWED_EVENT_KEYS
    if unknown_event_keys:
        raise InvalidHardwareEvent("unsupported_event_keys")
    external_event_id = str(data.get("event_id") or "").strip()
    if not external_event_id or len(external_event_id) > 180:
        raise InvalidHardwareEvent("invalid_event_id")
    try:
        event_type = HardwareEventType(str(data.get("event_type") or ""))
    except ValueError as exc:
        raise InvalidHardwareEvent("invalid_event_type") from exc
    occurred_raw = data.get("occurred_at")
    try:
        occurred_at = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise InvalidHardwareEvent("invalid_occurred_at") from exc
    if occurred_at.tzinfo is None:
        raise InvalidHardwareEvent("timezone_required")
    occurred_at = occurred_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if occurred_at < now - MAX_EVENT_AGE:
        raise InvalidHardwareEvent("stale_event")
    if occurred_at > now + MAX_EVENT_FUTURE_SKEW:
        raise InvalidHardwareEvent("future_event")
    credential = data.get("credential")
    if credential is not None:
        credential = str(credential).strip()
        if not credential or len(credential) > 256:
            raise InvalidHardwareEvent("invalid_credential")
    raw_payload = data.get("payload")
    if raw_payload is None:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raise InvalidHardwareEvent("invalid_payload")
    unknown_payload_keys = set(raw_payload) - ALLOWED_PAYLOAD_KEYS
    if unknown_payload_keys:
        raise InvalidHardwareEvent("unsupported_payload_keys")
    payload = {key: raw_payload[key] for key in ALLOWED_PAYLOAD_KEYS if key in raw_payload}
    return HardwareEvent(
        tenant_id=int(device["condominio_id"]),
        device_id=str(device["id"]),
        event_id=external_event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        credential=credential,
        payload=payload,
    )
