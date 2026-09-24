import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Callable
from .contracts import HardwareCommand, HardwareCommandType, HardwareEvent, HardwareEventType


@dataclass(frozen=True)
class AccessDecision:
    granted: bool
    reason: str
    command: HardwareCommand | None = None


def credential_fingerprint(value: str, key: str | bytes | None = None) -> str:
    """Keyed stable lookup value. Production must provide HARDWARE_CREDENTIAL_HMAC_KEY."""
    material = key if key is not None else os.getenv("HARDWARE_CREDENTIAL_HMAC_KEY")
    if material is None:
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError("HARDWARE_CREDENTIAL_HMAC_KEY is required in production.")
        material = "development-only-hardware-credential-key"
    key_bytes = material.encode("utf-8") if isinstance(material, str) else material
    if len(key_bytes) < 32:
        raise RuntimeError("HARDWARE_CREDENTIAL_HMAC_KEY must be at least 32 bytes.")
    normalized = value.strip().encode("utf-8")
    return hmac.new(key_bytes, normalized, hashlib.sha256).hexdigest()


class AccessDecisionService:
    """Pure access-decision orchestration; vendor I/O remains outside this service."""

    def __init__(self, *, credential_lookup: Callable, authorization_check: Callable, command_id_factory: Callable):
        self.credential_lookup = credential_lookup
        self.authorization_check = authorization_check
        self.command_id_factory = command_id_factory

    def decide(self, event: HardwareEvent) -> AccessDecision:
        if event.event_type != HardwareEventType.CREDENTIAL_READ or not event.credential:
            return AccessDecision(False, "unsupported_event")
        fingerprint = credential_fingerprint(event.credential)
        credential = self.credential_lookup(event.tenant_id, fingerprint)
        if not credential or not credential.get("ativo"):
            return AccessDecision(False, "credential_unknown_or_inactive")
        if int(credential["condominio_id"]) != int(event.tenant_id):
            return AccessDecision(False, "tenant_mismatch")
        if not self.authorization_check(event.tenant_id, credential, event.device_id):
            return AccessDecision(False, "access_not_authorized")
        command = HardwareCommand(
            tenant_id=event.tenant_id,
            device_id=event.device_id,
            command_id=self.command_id_factory(),
            command_type=HardwareCommandType.GRANT_ACCESS,
            payload={"source_event_id": event.event_id},
        )
        return AccessDecision(True, "authorized", command)
