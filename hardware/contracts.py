from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional


class HardwareEventType(str, Enum):
    CREDENTIAL_READ = "credential_read"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    DEVICE_STATUS = "device_status"
    DOOR_STATE = "door_state"


class HardwareCommandType(str, Enum):
    GRANT_ACCESS = "grant_access"
    SYNC_CREDENTIAL = "sync_credential"
    REVOKE_CREDENTIAL = "revoke_credential"
    PING = "ping"


@dataclass(frozen=True)
class HardwareEvent:
    tenant_id: int
    device_id: str
    event_id: str
    event_type: HardwareEventType
    occurred_at: datetime
    credential: Optional[str] = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def now(cls, *, tenant_id: int, device_id: str, event_id: str, event_type: HardwareEventType,
            credential: Optional[str] = None, payload: Optional[Mapping[str, Any]] = None):
        return cls(tenant_id, device_id, event_id, event_type, datetime.now(timezone.utc), credential, payload or {})


@dataclass(frozen=True)
class HardwareCommand:
    tenant_id: int
    device_id: str
    command_id: str
    command_type: HardwareCommandType
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    external_id: Optional[str] = None
    detail: Optional[str] = None
