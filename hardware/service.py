import uuid
from database.connection import conectar, liberar
from .access import AccessDecisionService
from .policy import evaluate_access_policies
from .processor import HardwareEventProcessor
from .repository import HardwareRepository


class HardwareAccessService:
    """Atomic ingest + policy decision + outbox enqueue. It performs no device I/O."""

    def __init__(self, *, command_id_factory=None):
        self.command_id_factory = command_id_factory or (lambda: str(uuid.uuid4()))

    def ingest(self, event):
        conn = conectar()
        try:
            repo = HardwareRepository(conn)
            processor = HardwareEventProcessor(
                device_lookup=repo.get_device,
                event_exists=repo.event_exists,
                persist_event=repo.persist_event,
            )
            processed = processor.process(event)
            if not processed.accepted or processed.duplicate:
                conn.commit()
                return processed, None

            def authorization_check(tenant_id, credential, device_id):
                device = repo.get_device(tenant_id, device_id)
                if not device or not repo.device_is_online(tenant_id, device_id):
                    return False
                policies = repo.list_access_policies(tenant_id, credential["id"])
                decision = evaluate_access_policies(
                    policies,
                    device_id=device_id,
                    zone=(device.get("configuracao") or {}).get("zona"),
                    at=event.occurred_at,
                )
                return decision.allowed

            decision_service = AccessDecisionService(
                credential_lookup=lambda tenant, fingerprint: repo.get_credential_by_fingerprint(tenant, fingerprint),
                authorization_check=authorization_check,
                command_id_factory=self.command_id_factory,
            )
            decision = decision_service.decide(event)
            repo.record_access_decision(event, granted=decision.granted, reason=decision.reason)
            if decision.command is not None:
                repo.enqueue_command(decision.command)
            conn.commit()
            return processed, decision
        except Exception:
            conn.rollback()
            raise
        finally:
            liberar(conn)
