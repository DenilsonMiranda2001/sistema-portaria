from hardware.adapter import AdapterRegistry
from hardware.contracts import HardwareCommand, HardwareCommandType
from hardware.processor import HardwareEventProcessor
from hardware.simulator import SimulatorAdapter


def test_simulator_and_registry_are_vendor_neutral():
    registry = AdapterRegistry()
    simulator = SimulatorAdapter()
    registry.register(simulator)
    assert registry.get("simulator") is simulator
    event = simulator.normalize_event(7, "device-1", {"event_id": "evt-1", "credential": "TAG-123"})
    assert event.tenant_id == 7
    assert event.credential == "TAG-123"


def test_processor_enforces_tenant_and_idempotency():
    recorded = []
    processor = HardwareEventProcessor(
        device_lookup=lambda tenant, device: {"condominio_id": tenant, "ativo": True},
        event_exists=lambda tenant, device, event: bool(recorded),
        persist_event=recorded.append,
    )
    event = SimulatorAdapter().normalize_event(3, "gate-a", {"event_id": "same"})
    first = processor.process(event)
    second = processor.process(event)
    assert first.accepted and not first.duplicate
    assert second.accepted and second.duplicate
    assert len(recorded) == 1


def test_simulator_never_contacts_physical_hardware():
    adapter = SimulatorAdapter()
    command = HardwareCommand(1, "gate-a", "cmd-1", HardwareCommandType.PING)
    result = adapter.send_command(command)
    assert result.accepted
    assert adapter.commands == [command]


def test_processor_rejects_revoked_device_even_if_event_bypasses_http_auth():
    recorded = []
    processor = HardwareEventProcessor(
        device_lookup=lambda tenant, device: {
            "condominio_id": tenant,
            "ativo": True,
            "auth_revoked_em": "2026-09-24T00:00:00Z",
        },
        event_exists=lambda tenant, device, event: False,
        persist_event=recorded.append,
    )
    event = SimulatorAdapter().normalize_event(3, "gate-revoked", {"event_id": "evt-revoked"})
    result = processor.process(event)
    assert result.accepted is False
    assert result.reason == "unknown_inactive_or_revoked_device"
    assert recorded == []
