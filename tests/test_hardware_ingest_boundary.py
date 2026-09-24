from hardware.ingest import build_authenticated_event, InvalidHardwareEvent


DEVICE = {"id": "00000000-0000-0000-0000-000000000001", "condominio_id": 7}


def test_caller_cannot_choose_tenant_or_device():
    event = build_authenticated_event(DEVICE, {
        "tenant_id": 999, "device_id": "attacker-device", "event_id": "evt-1",
        "event_type": "credential_read", "occurred_at": "2026-09-24T10:00:00-03:00",
        "credential": "tag-1",
    })
    assert event.tenant_id == 7
    assert event.device_id == DEVICE["id"]


def test_payload_is_allowlisted():
    event = build_authenticated_event(DEVICE, {
        "event_id": "evt-2", "event_type": "device_status",
        "occurred_at": "2026-09-24T13:00:00Z",
        "payload": {"reader": "A", "direction": "entry"},
    })
    assert event.payload == {"reader": "A", "direction": "entry"}


def test_unknown_payload_fields_are_rejected_fail_closed():
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-unknown", "event_type": "device_status",
            "occurred_at": "2026-09-24T13:00:00Z",
            "payload": {"reader": "A", "unexpected_vendor_field": "value"},
        })
    except InvalidHardwareEvent as exc:
        assert str(exc) == "unsupported_payload_keys"
    else:
        raise AssertionError("unknown payload field accepted")


def test_naive_timestamp_is_rejected():
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-3", "event_type": "door_state",
            "occurred_at": "2026-09-24T13:00:00",
        })
    except InvalidHardwareEvent as exc:
        assert str(exc) == "timezone_required"
    else:
        raise AssertionError("naive timestamp accepted")
