import json
from datetime import datetime, timezone
from .access import credential_fingerprint
from .contracts import HardwareCommand, HardwareEvent


class HardwareRepository:
    """PostgreSQL persistence boundary. Callers own commit/rollback."""

    def __init__(self, conn):
        self.conn = conn

    def get_device(self, tenant_id: int, device_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, vendor, external_device_id, nome, tipo, ativo,
                                  ultimo_heartbeat_em
                           FROM hardware_devices
                           WHERE condominio_id=%s AND id=%s::uuid""", (tenant_id, device_id))
            return cur.fetchone()

    def get_credential(self, tenant_id: int, raw_credential: str):
        fingerprint = credential_fingerprint(raw_credential)
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, tipo, morador_id, visitante_id, ativo
                           FROM hardware_credentials
                           WHERE condominio_id=%s AND identificador_hash=%s""", (tenant_id, fingerprint))
            return cur.fetchone()

    def event_exists(self, tenant_id: int, device_id: str, external_event_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("""SELECT 1 FROM hardware_events
                           WHERE condominio_id=%s AND device_id=%s::uuid AND external_event_id=%s""",
                        (tenant_id, device_id, external_event_id))
            return cur.fetchone() is not None

    def persist_event(self, event: HardwareEvent):
        credential_hash = credential_fingerprint(event.credential) if event.credential else None
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_events
                (condominio_id, device_id, external_event_id, tipo, credential_hash, payload, ocorrido_em)
                VALUES (%s,%s::uuid,%s,%s,%s,%s::jsonb,%s)
                ON CONFLICT (condominio_id, device_id, external_event_id) DO NOTHING""",
                (event.tenant_id, event.device_id, event.event_id, event.event_type.value,
                 credential_hash, json.dumps(dict(event.payload), ensure_ascii=False), event.occurred_at))

    def enqueue_command(self, command: HardwareCommand):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_commands
                (id, condominio_id, device_id, tipo, payload, proxima_tentativa_em)
                VALUES (%s::uuid,%s,%s::uuid,%s,%s::jsonb,%s)
                ON CONFLICT (id) DO NOTHING""",
                (command.command_id, command.tenant_id, command.device_id, command.command_type.value,
                 json.dumps(dict(command.payload), ensure_ascii=False), datetime.now(timezone.utc)))

    def mark_heartbeat(self, tenant_id: int, device_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_devices SET ultimo_heartbeat_em=CURRENT_TIMESTAMP,
                           atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo""", (tenant_id, device_id))
            return cur.rowcount == 1

    def expire_commands(self):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_commands SET status='expired', atualizado_em=CURRENT_TIMESTAMP
                           WHERE status IN ('pending','failed')
                             AND expira_em IS NOT NULL AND expira_em <= CURRENT_TIMESTAMP""")
            return cur.rowcount

    def claim_pending_commands(self, limit: int = 20):
        with self.conn.cursor() as cur:
            cur.execute("""WITH claimed AS (
                    SELECT id FROM hardware_commands
                    WHERE status IN ('pending','failed')
                      AND (expira_em IS NULL OR expira_em > CURRENT_TIMESTAMP)
                      AND (proxima_tentativa_em IS NULL OR proxima_tentativa_em <= CURRENT_TIMESTAMP)
                    ORDER BY criado_em
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                )
                UPDATE hardware_commands c
                SET status='processing', tentativas=tentativas+1, atualizado_em=CURRENT_TIMESTAMP
                FROM claimed WHERE c.id=claimed.id
                RETURNING c.id::text, c.condominio_id, c.device_id::text, c.tipo, c.payload, c.tentativas""", (limit,))
            return cur.fetchall()

    def finish_command(self, command_id: str, *, succeeded: bool, error: str | None = None, retry_seconds: int = 5):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_commands
                           SET status=%s, erro=%s,
                               proxima_tentativa_em=CASE WHEN %s THEN NULL ELSE CURRENT_TIMESTAMP + (%s * INTERVAL '1 second') END,
                               concluido_em=CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                               atualizado_em=CURRENT_TIMESTAMP
                           WHERE id=%s::uuid AND status='processing'""",
                        ("succeeded" if succeeded else "failed",
                         None if succeeded else (error or "adapter_error")[:1000],
                         succeeded, retry_seconds, succeeded, command_id))
