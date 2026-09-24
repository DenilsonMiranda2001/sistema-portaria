import json
from database.connection import conectar, liberar
from .auth import verify_device_request
from .ingest import InvalidHardwareEvent, build_authenticated_event
from .repository import HardwareRepository
from .service import HardwareAccessService


class HardwareHttpError(ValueError):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def ingest_simulator_request(*, headers, body: bytes, presented_secret: str):
    """Authenticate and ingest a simulator event. No physical adapter is invoked."""
    key_id = (headers.get("X-Hardware-Key-Id") or "").strip()
    timestamp = (headers.get("X-Hardware-Timestamp") or "").strip()
    nonce = (headers.get("X-Hardware-Nonce") or "").strip()
    signature = (headers.get("X-Hardware-Signature") or "").strip()
    if not all((key_id, timestamp, nonce, signature, presented_secret)):
        raise HardwareHttpError(401, "hardware_auth_required")

    conn = conectar()
    try:
        repo = HardwareRepository(conn)
        def lookup(value):
            device = repo.get_device_auth_identity(value)
            if device:
                device["_presented_secret"] = presented_secret
            return device
        auth = verify_device_request(
            key_id=key_id, timestamp=timestamp, nonce=nonce, signature=signature, body=body,
            device_lookup=lookup, nonce_consume=repo.consume_auth_nonce,
        )
        if not auth.authenticated:
            conn.rollback()
            raise HardwareHttpError(401, "hardware_auth_failed")
        conn.commit()
        device = auth.device
    except HardwareHttpError:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)

    if device.get("vendor") not in (None, "simulator"):
        raise HardwareHttpError(403, "physical_hardware_disabled")
    try:
        data = json.loads(body.decode("utf-8"))
        event = build_authenticated_event(device, data)
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidHardwareEvent) as exc:
        raise HardwareHttpError(400, "invalid_hardware_event") from exc
    return HardwareAccessService().ingest(event)
