from hardware.repository import HardwareRepository


def test_sensitive_event_payload_keys_are_removed_before_persistence():
    payload = {
        "reader": "A", "credential": "123", "TAG": "456", "token": "abc",
        "password": "pw", "secret": "s", "authorization": "bearer",
        "cpf": "000", "document": "doc",
    }
    safe = HardwareRepository._safe_event_payload(payload)
    assert safe == {"reader": "A"}
