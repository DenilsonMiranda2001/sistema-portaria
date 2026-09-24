from database.connection import conectar, liberar
from .access import AccessDecisionService
from .processor import HardwareEventProcessor
from .repository import HardwareRepository


class HardwareAccessService:
    """Atomic ingest + decision + outbox enqueue. It performs no device I/O."""

    def __init__(self, *, command_id_factory, authorization_check):
        self.command_id_factory = command_id_factory
        self.authorization_check = authorization_check

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

            decision_service = AccessDecisionService(
                credential_lookup=lambda tenant, fingerprint: self._lookup_by_fingerprint(repo, tenant, fingerprint),
                authorization_check=self.authorization_check,
                command_id_factory=self.command_id_factory,
            )
            decision = decision_service.decide(event)
            if decision.command is not None:
                repo.enqueue_command(decision.command)
            conn.commit()
            return processed, decision
        except Exception:
            conn.rollback()
            raise
        finally:
            liberar(conn)

    @staticmethod
    def _lookup_by_fingerprint(repo, tenant_id, fingerprint):
        with repo.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, tipo, morador_id, visitante_id, ativo
                           FROM hardware_credentials
                           WHERE condominio_id=%s AND identificador_hash=%s""", (tenant_id, fingerprint))
            return cur.fetchone()
