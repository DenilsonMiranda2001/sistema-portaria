import logging
from .contracts import HardwareCommand, HardwareCommandType
from .repository import HardwareRepository

logger = logging.getLogger(__name__)


def dispatch_claimed_commands(conn, registry, limit=20):
    """Dispatch an already durable outbox. Designed for a separate worker process."""
    repo = HardwareRepository(conn)
    commands = repo.claim_pending_commands(limit)
    completed = 0
    for row in commands:
        try:
            device = repo.get_device(row["condominio_id"], row["device_id"])
            if not device or not device["ativo"]:
                raise RuntimeError("device_unavailable")
            adapter = registry.get(device["vendor"])
            command = HardwareCommand(
                tenant_id=row["condominio_id"],
                device_id=row["device_id"],
                command_id=row["id"],
                command_type=HardwareCommandType(row["tipo"]),
                payload=row["payload"] or {},
            )
            result = adapter.send_command(command)
            repo.finish_command(row["id"], succeeded=result.accepted, error=result.detail)
            completed += int(result.accepted)
        except Exception as exc:
            logger.exception("Hardware command dispatch failed command_id=%s", row["id"])
            repo.finish_command(row["id"], succeeded=False, error=type(exc).__name__)
    conn.commit()
    return {"claimed": len(commands), "succeeded": completed}
