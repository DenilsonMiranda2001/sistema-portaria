from abc import ABC, abstractmethod
from typing import Iterable
from .contracts import CommandResult, HardwareCommand, HardwareEvent


class HardwareAdapter(ABC):
    """Vendor boundary. Adapters translate vendor protocols only."""

    vendor: str

    @abstractmethod
    def normalize_event(self, tenant_id: int, device_id: str, raw_event: dict) -> HardwareEvent:
        raise NotImplementedError

    @abstractmethod
    def send_command(self, command: HardwareCommand) -> CommandResult:
        raise NotImplementedError

    def healthcheck(self) -> bool:
        return True


class AdapterRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, adapter: HardwareAdapter):
        if not adapter.vendor:
            raise ValueError("adapter vendor is required")
        self._adapters[adapter.vendor] = adapter

    def get(self, vendor: str) -> HardwareAdapter:
        try:
            return self._adapters[vendor]
        except KeyError as exc:
            raise LookupError(f"unsupported hardware vendor: {vendor}") from exc

    def vendors(self) -> Iterable[str]:
        return tuple(sorted(self._adapters))
