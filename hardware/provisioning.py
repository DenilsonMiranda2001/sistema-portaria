import secrets
import uuid
from dataclasses import dataclass
from .auth import secret_verifier


@dataclass(frozen=True)
class ProvisionedDevice:
    device_id: str
    key_id: str
    secret: str


def provision_simulator_device(repo, *, tenant_id: int, name: str, device_type: str = "simulator") -> ProvisionedDevice:
    """Provision a simulator identity. The plaintext secret is returned exactly once."""
    device_id = str(uuid.uuid4())
    key_id = "hw_" + secrets.token_urlsafe(18)
    secret = secrets.token_urlsafe(32)
    repo.create_device_identity(
        device_id=device_id,
        tenant_id=tenant_id,
        vendor="simulator",
        external_device_id="sim-" + device_id,
        name=name,
        device_type=device_type,
        key_id=key_id,
        secret_hash=secret_verifier(secret),
    )
    return ProvisionedDevice(device_id=device_id, key_id=key_id, secret=secret)


def rotate_simulator_secret(repo, *, tenant_id: int, device_id: str) -> str:
    """Rotate a simulator secret and return the new plaintext value exactly once."""
    secret = secrets.token_urlsafe(32)
    if not repo.rotate_device_secret(tenant_id, device_id, secret_verifier(secret)):
        raise LookupError("device_not_found_or_inactive")
    return secret


def revoke_device_auth(repo, *, tenant_id: int, device_id: str) -> bool:
    return repo.revoke_device_auth(tenant_id, device_id)
