from dataclasses import dataclass
from typing import Callable
from .contracts import HardwareEvent


@dataclass(frozen=True)
class ProcessResult:
    accepted: bool
    duplicate: bool = False
    reason: str = ""


class HardwareEventProcessor:
    """Application boundary with explicit tenant and idempotency enforcement."""

    def __init__(self, *, device_lookup: Callable, event_exists: Callable, persist_event: Callable):
        self.device_lookup = device_lookup
        self.event_exists = event_exists
        self.persist_event = persist_event

    def process(self, event: HardwareEvent) -> ProcessResult:
        device = self.device_lookup(event.tenant_id, event.device_id)
        if not device or not device.get("ativo"):
            return ProcessResult(False, reason="unknown_or_inactive_device")
        if int(device["condominio_id"]) != int(event.tenant_id):
            return ProcessResult(False, reason="tenant_mismatch")
        if self.event_exists(event.tenant_id, event.device_id, event.event_id):
            return ProcessResult(True, duplicate=True, reason="duplicate")
        self.persist_event(event)
        return ProcessResult(True, reason="recorded")
