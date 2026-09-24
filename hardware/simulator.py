import uuid
from .adapter import HardwareAdapter
from .contracts import CommandResult, HardwareCommand, HardwareEvent, HardwareEventType


class SimulatorAdapter(HardwareAdapter):
    vendor = "simulator"

    def __init__(self):
        self.commands = []

    def normalize_event(self, tenant_id: int, device_id: str, raw_event: dict) -> HardwareEvent:
        event_type = HardwareEventType(raw_event.get("type", HardwareEventType.CREDENTIAL_READ.value))
        return HardwareEvent.now(
            tenant_id=tenant_id,
            device_id=device_id,
            event_id=str(raw_event.get("event_id") or uuid.uuid4()),
            event_type=event_type,
            credential=raw_event.get("credential"),
            payload=raw_event.get("payload") or {},
        )

    def send_command(self, command: HardwareCommand) -> CommandResult:
        self.commands.append(command)
        return CommandResult(True, external_id=f"sim:{command.command_id}", detail="simulated")
