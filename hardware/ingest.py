from datetime import datetime, timezone
from .contracts import HardwareEvent, HardwareEventType


ALLOWED_PAYLOAD_KEYS = {"reader", "direction", "door", "zone", "signal", "source"}


class InvalidHardwareEvent(ValueError):
    pass


def build_authenticated_event(device: dict, data: dict) -> HardwareEvent:
    """Build an event only from an authenticated device identity.

    Tenant and device identifiers supplied by callers are deliberately ignored.
    """
    if not isinstance(data, dict):
        raise InvalidHardwareEvent("invalid_json")
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
    credential = data.get("credential")
    if credential is not None:
        credential = str(credential).strip()
        if not credential or len(credential) > 256:
            raise InvalidHardwareEvent("invalid_credential")
    raw_payload = data.get("payload") or {}
    if not isinstance(raw_payload, dict):
        raise InvalidHardwareEvent("invalid_payload")
    payload = {key: raw_payload[key] for key in ALLOWED_PAYLOAD_KEYS if key in raw_payload}
    return HardwareEvent(
        tenant_id=int(device["condominio_id"]),
        device_id=str(device["id"]),
        event_id=external_event_id,
        event_type=event_type,
        occurred_at=occurred_at.astimezone(timezone.utc),
        credential=credential,
        payload=payload,
    )
