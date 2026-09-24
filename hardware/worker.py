import logging
from database.connection import conectar, liberar
from .contracts import HardwareCommand, HardwareCommandType
from .repository import HardwareRepository

logger = logging.getLogger(__name__)


def claim_command_batch(limit=20):
    """Claim commands durably and release the database transaction before device I/O."""
    conn = conectar()
    try:
        repo = HardwareRepository(conn)
        repo.recover_stuck_commands()
        repo.expire_commands()
        commands = repo.claim_pending_commands(limit)
        conn.commit()
        return commands
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def finish_dispatched_command(command_id, *, succeeded, error=None, retry_seconds=5):
    """Persist one command outcome in its own short transaction."""
    conn = conectar()
    try:
        HardwareRepository(conn).finish_command(
            command_id, succeeded=succeeded, error=error, retry_seconds=retry_seconds
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)



def _access_command_still_authorized(tenant_id, command_id, device_id):
    conn = conectar()
    try:
        valid = HardwareRepository(conn).access_command_still_authorized(tenant_id, command_id, device_id)
        conn.commit()
        return valid
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def _load_device(tenant_id, device_id):
    conn = conectar()
    try:
        device = HardwareRepository(conn).get_device(tenant_id, device_id)
        conn.commit()
        return device
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def dispatch_claimed_commands(registry, limit=20):
    """Dispatch durable outbox commands without holding a DB transaction during device I/O."""
    commands = claim_command_batch(limit)
    completed = 0
    for row in commands:
        retry_seconds = min(300, 5 * (2 ** max(0, row["tentativas"] - 1)))
        try:
            device = _load_device(row["condominio_id"], row["device_id"])
            if not device or not device["ativo"]:
                raise RuntimeError("device_unavailable")
            if row["tipo"] == HardwareCommandType.GRANT_ACCESS.value:
                if not _access_command_still_authorized(row["condominio_id"], row["id"], row["device_id"]):
                    finish_dispatched_command(row["id"], succeeded=False, error="authorization_revoked", retry_seconds=300)
                    continue
            adapter = registry.get(device["vendor"])
            command = HardwareCommand(
                tenant_id=row["condominio_id"],
                device_id=row["device_id"],
                command_id=row["id"],
                command_type=HardwareCommandType(row["tipo"]),
                payload=row["payload"] or {},
            )
            result = adapter.send_command(command)
            finish_dispatched_command(
                row["id"],
                succeeded=result.accepted,
                error=None if result.accepted else "adapter_rejected",
                retry_seconds=retry_seconds,
            )
            completed += int(result.accepted)
        except Exception as exc:
            logger.error(
                "Hardware command dispatch failed command_id=%s error_type=%s",
                row["id"], type(exc).__name__
            )
            finish_dispatched_command(
                row["id"], succeeded=False, error=type(exc).__name__, retry_seconds=retry_seconds
            )
    return {"claimed": len(commands), "succeeded": completed}
