from datetime import datetime, timedelta, timezone

from hardware.ingest import build_authenticated_event, InvalidHardwareEvent


DEVICE = {"id": "00000000-0000-0000-0000-000000000001", "condominio_id": 7}


def test_tenant_and_device_identity_come_only_from_authenticated_device():
    event = build_authenticated_event(DEVICE, {
        "event_id": "evt-1",
        "event_type": "credential_read",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "credential": "tag-1",
    })
    assert event.tenant_id == 7
    assert event.device_id == DEVICE["id"]


def test_caller_supplied_tenant_or_device_identity_is_rejected():
    for field, value in (("tenant_id", 999), ("device_id", "attacker-device")):
        try:
            build_authenticated_event(DEVICE, {
                "event_id": f"evt-{field}",
                "event_type": "credential_read",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "credential": "tag-1",
                field: value,
            })
        except InvalidHardwareEvent as exc:
            assert str(exc) == "unsupported_event_keys"
        else:
            raise AssertionError(f"caller-controlled {field} accepted")


def test_payload_is_allowlisted():
    event = build_authenticated_event(DEVICE, {
        "event_id": "evt-2", "event_type": "device_status",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"reader": "A", "direction": "entry"},
    })
    assert event.payload == {"reader": "A", "direction": "entry"}


def test_unknown_payload_fields_are_rejected_fail_closed():
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-unknown", "event_type": "device_status",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
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


def test_stale_event_is_rejected():
    stale = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-stale", "event_type": "credential_read",
            "occurred_at": stale, "credential": "tag-1",
        })
    except InvalidHardwareEvent as exc:
        assert str(exc) == "stale_event"
    else:
        raise AssertionError("stale event accepted")


def test_event_too_far_in_future_is_rejected():
    future = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-future", "event_type": "credential_read",
            "occurred_at": future, "credential": "tag-1",
        })
    except InvalidHardwareEvent as exc:
        assert str(exc) == "future_event"
    else:
        raise AssertionError("future event accepted")


def test_unknown_event_envelope_fields_are_rejected_fail_closed():
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-envelope",
            "event_type": "device_status",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"reader": "A"},
            "unexpected_top_level_field": "value",
        })
    except InvalidHardwareEvent as exc:
        assert str(exc) == "unsupported_event_keys"
    else:
        raise AssertionError("unknown event envelope field accepted")



def test_event_freshness_exact_boundaries_are_accepted():
    now = datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)
    for event_id, occurred_at in (
        ("evt-age-boundary", now - timedelta(minutes=5)),
        ("evt-future-boundary", now + timedelta(minutes=1)),
    ):
        event = build_authenticated_event(DEVICE, {
            "event_id": event_id,
            "event_type": "credential_read",
            "occurred_at": occurred_at.isoformat(),
            "credential": "tag-1",
        }, now=now)
        assert event.event_id == event_id


def test_event_freshness_just_outside_boundaries_is_rejected():
    now = datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)
    cases = (
        ("evt-too-old", now - timedelta(minutes=5, microseconds=1), "stale_event"),
        ("evt-too-future", now + timedelta(minutes=1, microseconds=1), "future_event"),
    )
    for event_id, occurred_at, expected in cases:
        try:
            build_authenticated_event(DEVICE, {
                "event_id": event_id,
                "event_type": "credential_read",
                "occurred_at": occurred_at.isoformat(),
                "credential": "tag-1",
            }, now=now)
        except InvalidHardwareEvent as exc:
            assert str(exc) == expected
        else:
            raise AssertionError(f"{event_id} accepted outside freshness boundary")


def test_injected_clock_must_be_timezone_aware():
    try:
        build_authenticated_event(DEVICE, {
            "event_id": "evt-clock",
            "event_type": "device_status",
            "occurred_at": "2026-09-24T13:00:00+00:00",
        }, now=datetime(2026, 9, 24, 13, 0))
    except ValueError as exc:
        assert str(exc) == "now must be timezone-aware"
    else:
        raise AssertionError("naive injected clock accepted")
