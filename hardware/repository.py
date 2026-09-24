import json
from datetime import datetime, timedelta, timezone
from .access import credential_fingerprint
from .contracts import HardwareCommand, HardwareEvent


class HardwareRepository:
    """PostgreSQL persistence boundary. Callers own commit/rollback."""

    def __init__(self, conn):
        self.conn = conn

    def list_access_zone_operational_status(self, tenant_id: int, stale_seconds: int = 90):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT z.id::text, z.nome, z.codigo, z.ativo,
                                  COUNT(d.id) FILTER (WHERE d.ativo) AS active_devices,
                                  COUNT(d.id) FILTER (
                                    WHERE d.ativo
                                      AND d.auth_revoked_em IS NULL
                                      AND d.ultimo_heartbeat_em IS NOT NULL
                                      AND d.ultimo_heartbeat_em >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                                  ) AS online_devices,
                                  CASE
                                    WHEN NOT z.ativo THEN 'inactive'
                                    WHEN COUNT(d.id) FILTER (WHERE d.ativo) = 0 THEN 'no_device'
                                    WHEN COUNT(d.id) FILTER (
                                      WHERE d.ativo
                                        AND d.auth_revoked_em IS NULL
                                        AND d.ultimo_heartbeat_em IS NOT NULL
                                        AND d.ultimo_heartbeat_em >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                                    ) = 0 THEN 'unavailable'
                                    ELSE 'operational'
                                  END AS operational_status
                           FROM hardware_access_zones z
                           LEFT JOIN hardware_devices d
                             ON d.access_zone_id=z.id AND d.condominio_id=z.condominio_id
                           WHERE z.condominio_id=%s
                           GROUP BY z.id,z.nome,z.codigo,z.ativo
                           ORDER BY z.nome""", (stale_seconds, stale_seconds, tenant_id))
            return cur.fetchall()

    def list_access_zones(self, tenant_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, nome, codigo, descricao, ativo, criado_em
                           FROM hardware_access_zones WHERE condominio_id=%s
                           ORDER BY nome""", (tenant_id,))
            return cur.fetchall()

    def create_access_zone(self, *, zone_id, tenant_id, name, code, description=None):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_access_zones(id,condominio_id,nome,codigo,descricao)
                           VALUES (%s::uuid,%s,%s,%s,%s) RETURNING id::text""",
                        (zone_id, tenant_id, name, code, description))
            return cur.fetchone()["id"]

    def deactivate_access_zone(self, tenant_id: int, zone_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_access_zones SET ativo=FALSE, atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo""", (tenant_id, zone_id))
            return cur.rowcount == 1

    def list_device_operational_status(self, tenant_id: int, stale_seconds: int = 90):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT d.id::text, d.nome, d.vendor, d.tipo, d.ativo, d.ultimo_heartbeat_em,
                                  d.access_zone_id::text, z.nome AS access_zone_nome,
                                  CASE
                                    WHEN NOT d.ativo THEN 'inactive'
                                    WHEN d.auth_revoked_em IS NOT NULL THEN 'auth_revoked'
                                    WHEN d.access_zone_id IS NULL THEN 'unassigned'
                                    WHEN d.ultimo_heartbeat_em IS NULL THEN 'never_seen'
                                    WHEN d.ultimo_heartbeat_em < CURRENT_TIMESTAMP - (%s * INTERVAL '1 second') THEN 'offline'
                                    ELSE 'online'
                                  END AS operational_status
                           FROM hardware_devices d
                           LEFT JOIN hardware_access_zones z
                             ON z.id=d.access_zone_id AND z.condominio_id=d.condominio_id
                           WHERE d.condominio_id=%s
                           ORDER BY d.nome""", (stale_seconds, tenant_id))
            return cur.fetchall()

    def list_devices(self, tenant_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT d.id::text, d.vendor, d.external_device_id, d.nome, d.tipo, d.ativo,
                                  d.ultimo_heartbeat_em, d.auth_key_id, d.auth_secret_rotated_em, d.auth_revoked_em,
                                  d.access_zone_id::text, z.nome AS access_zone_nome, z.codigo AS access_zone_codigo
                           FROM hardware_devices d
                           LEFT JOIN hardware_access_zones z
                             ON z.id=d.access_zone_id AND z.condominio_id=d.condominio_id
                           WHERE d.condominio_id=%s
                           ORDER BY d.nome, d.criado_em""", (tenant_id,))
            return cur.fetchall()

    def assign_device_zone(self, tenant_id: int, device_id: str, zone_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_devices d
                           SET access_zone_id=z.id, atualizado_em=CURRENT_TIMESTAMP
                           FROM hardware_access_zones z
                           WHERE d.condominio_id=%s AND d.id=%s::uuid
                             AND z.condominio_id=d.condominio_id AND z.id=%s::uuid AND z.ativo
                           RETURNING d.id::text""", (tenant_id, device_id, zone_id))
            row = cur.fetchone()
            return row["id"] if row else None

    def create_device_identity(self, *, device_id, tenant_id, vendor, external_device_id, name, device_type, key_id, secret_hash):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_devices
                (id, condominio_id, vendor, external_device_id, nome, tipo, auth_key_id, auth_secret_hash, auth_secret_rotated_em)
                VALUES (%s::uuid,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)""",
                (device_id, tenant_id, vendor, external_device_id, name, device_type, key_id, secret_hash))

    def rotate_device_secret(self, tenant_id: int, device_id: str, secret_hash: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_devices
                           SET auth_secret_hash=%s, auth_secret_rotated_em=CURRENT_TIMESTAMP,
                               auth_revoked_em=NULL, atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo AND vendor='simulator'""",
                        (secret_hash, tenant_id, device_id))
            return cur.rowcount == 1

    def revoke_device_auth(self, tenant_id: int, device_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_devices
                           SET auth_revoked_em=CURRENT_TIMESTAMP, atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND auth_revoked_em IS NULL""",
                        (tenant_id, device_id))
            return cur.rowcount == 1

    def get_device(self, tenant_id: int, device_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, vendor, external_device_id, nome, tipo, ativo,
                                  configuracao, ultimo_heartbeat_em
                           FROM hardware_devices
                           WHERE condominio_id=%s AND id=%s::uuid""", (tenant_id, device_id))
            return cur.fetchone()

    def list_credentials(self, tenant_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT hc.id::text, hc.tipo, hc.morador_id, hc.visitante_id, hc.ativo,
                                  hc.criado_em, m.nome AS morador_nome, v.nome AS visitante_nome
                           FROM hardware_credentials hc
                           LEFT JOIN moradores m ON m.id=hc.morador_id AND m.condominio_id=hc.condominio_id
                           LEFT JOIN visitantes v ON v.id=hc.visitante_id AND v.condominio_id=hc.condominio_id
                           WHERE hc.condominio_id=%s ORDER BY hc.criado_em DESC""", (tenant_id,))
            return cur.fetchall()

    def create_resident_credential(self, *, credential_id, tenant_id, credential_type, raw_identifier, resident_id):
        fingerprint = credential_fingerprint(raw_identifier)
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_credentials
                           (id,condominio_id,tipo,identificador_hash,morador_id)
                           SELECT %s::uuid,%s,%s,%s,m.id
                           FROM moradores m
                           WHERE m.id=%s AND m.condominio_id=%s AND m.ativo
                           RETURNING id::text""",
                        (credential_id, tenant_id, credential_type, fingerprint, resident_id, tenant_id))
            row = cur.fetchone()
            return row["id"] if row else None

    def deactivate_credential(self, tenant_id: int, credential_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_credentials SET ativo=FALSE, atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo""",
                        (tenant_id, credential_id))
            return cur.rowcount == 1

    def get_credential(self, tenant_id: int, raw_credential: str):
        return self.get_credential_by_fingerprint(tenant_id, credential_fingerprint(raw_credential))

    def get_credential_by_fingerprint(self, tenant_id: int, fingerprint: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, tipo, morador_id, visitante_id, ativo
                           FROM hardware_credentials
                           WHERE condominio_id=%s AND identificador_hash=%s""", (tenant_id, fingerprint))
            return cur.fetchone()

    def get_device_auth_identity(self, key_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, vendor, ativo, auth_key_id, auth_secret_hash,
                                  auth_secret_rotated_em, auth_revoked_em
                           FROM hardware_devices WHERE auth_key_id=%s""", (key_id,))
            return cur.fetchone()

    def consume_auth_nonce(self, device_id: str, nonce_hash: str, expires_at):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM hardware_auth_nonces WHERE expira_em <= CURRENT_TIMESTAMP")
            cur.execute("""INSERT INTO hardware_auth_nonces(device_id, nonce_hash, expira_em)
                           VALUES (%s::uuid,%s,to_timestamp(%s))
                           ON CONFLICT (device_id, nonce_hash) DO NOTHING""",
                        (device_id, nonce_hash, expires_at))
            return cur.rowcount == 1

    def list_admin_access_policies(self, tenant_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT p.id::text, p.credential_id::text, p.device_id::text, p.zona,
                                  p.valido_de, p.valido_ate, p.dias_semana, p.hora_inicio, p.hora_fim,
                                  p.timezone, p.ativo, d.nome AS device_nome, z.nome AS access_zone_nome, c.tipo AS credential_tipo,
                                  m.nome AS morador_nome
                           FROM hardware_access_policies p
                           JOIN hardware_credentials c ON c.id=p.credential_id AND c.condominio_id=p.condominio_id
                           LEFT JOIN hardware_devices d ON d.id=p.device_id AND d.condominio_id=p.condominio_id
                           LEFT JOIN hardware_access_zones z ON z.id=p.access_zone_id AND z.condominio_id=p.condominio_id
                           LEFT JOIN moradores m ON m.id=c.morador_id AND m.condominio_id=c.condominio_id
                           WHERE p.condominio_id=%s ORDER BY p.criado_em DESC""", (tenant_id,))
            return cur.fetchall()

    def create_access_policy(self, *, policy_id, tenant_id, credential_id, device_id, weekdays,
                             start_time=None, end_time=None, timezone_name="America/Sao_Paulo"):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_access_policies
                           (id,condominio_id,credential_id,access_zone_id,dias_semana,hora_inicio,hora_fim,timezone)
                           SELECT %s::uuid,%s,c.id,z.id,%s::smallint[],%s,%s,%s
                           FROM hardware_credentials c
                           JOIN hardware_access_zones z ON z.id=%s::uuid AND z.condominio_id=%s AND z.ativo
                           WHERE c.id=%s::uuid AND c.condominio_id=%s AND c.ativo
                           RETURNING id::text""",
                        (policy_id, tenant_id, weekdays, start_time, end_time, timezone_name,
                         device_id, tenant_id, credential_id, tenant_id))
            row = cur.fetchone()
            return row["id"] if row else None

    def deactivate_access_policy(self, tenant_id: int, policy_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_access_policies SET ativo=FALSE
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo""", (tenant_id, policy_id))
            return cur.rowcount == 1

    def list_access_policies(self, tenant_id: int, credential_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id::text, condominio_id, credential_id::text, device_id::text,
                                  access_zone_id::text, zona, valido_de, valido_ate, dias_semana, hora_inicio, hora_fim, timezone, ativo
                           FROM hardware_access_policies
                           WHERE condominio_id=%s AND credential_id=%s::uuid AND ativo""",
                        (tenant_id, credential_id))
            return cur.fetchall()

    def event_exists(self, tenant_id: int, device_id: str, external_event_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("""SELECT 1 FROM hardware_events
                           WHERE condominio_id=%s AND device_id=%s::uuid AND external_event_id=%s""",
                        (tenant_id, device_id, external_event_id))
            return cur.fetchone() is not None

    @staticmethod
    def _safe_event_payload(payload):
        blocked = {"credential", "tag", "token", "password", "secret", "authorization", "document", "cpf"}
        return {str(k): v for k, v in dict(payload).items() if str(k).lower() not in blocked}

    def persist_event(self, event: HardwareEvent):
        credential_hash = credential_fingerprint(event.credential) if event.credential else None
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_events
                (condominio_id, device_id, external_event_id, tipo, credential_hash, payload, ocorrido_em)
                VALUES (%s,%s::uuid,%s,%s,%s,%s::jsonb,%s)
                ON CONFLICT (condominio_id, device_id, external_event_id) DO NOTHING
                RETURNING id""",
                (event.tenant_id, event.device_id, event.event_id, event.event_type.value,
                 credential_hash, json.dumps(self._safe_event_payload(event.payload), ensure_ascii=False), event.occurred_at))
            row = cur.fetchone()
            return row["id"] if row else None

    @staticmethod
    def _command_expiry(command: HardwareCommand, now: datetime):
        # Access-opening commands must never execute long after the originating event.
        if command.command_type.value == "grant_access":
            return now + timedelta(seconds=10)
        return now + timedelta(minutes=15)

    def enqueue_command(self, command: HardwareCommand):
        now = datetime.now(timezone.utc)
        expires_at = self._command_expiry(command, now)
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_commands
                (id, condominio_id, device_id, tipo, payload, proxima_tentativa_em, expira_em)
                VALUES (%s::uuid,%s,%s::uuid,%s,%s::jsonb,%s,%s)
                ON CONFLICT (id) DO NOTHING""",
                (command.command_id, command.tenant_id, command.device_id, command.command_type.value,
                 json.dumps(dict(command.payload), ensure_ascii=False), now, expires_at))

    def mark_heartbeat(self, tenant_id: int, device_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_devices SET ultimo_heartbeat_em=CURRENT_TIMESTAMP,
                           atualizado_em=CURRENT_TIMESTAMP
                           WHERE condominio_id=%s AND id=%s::uuid AND ativo""", (tenant_id, device_id))
            return cur.rowcount == 1

    def get_event_id(self, tenant_id: int, device_id: str, external_event_id: str):
        with self.conn.cursor() as cur:
            cur.execute("""SELECT id FROM hardware_events
                           WHERE condominio_id=%s AND device_id=%s::uuid AND external_event_id=%s""",
                        (tenant_id, device_id, external_event_id))
            row = cur.fetchone()
            return row["id"] if row else None

    def record_access_decision(self, event: HardwareEvent, *, granted: bool, reason: str, event_id=None):
        credential_hash = credential_fingerprint(event.credential) if event.credential else None
        internal_event_id = event_id if event_id is not None else self.get_event_id(
            event.tenant_id, event.device_id, event.event_id
        )
        if internal_event_id is None:
            raise RuntimeError("hardware_event_missing_for_decision")
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO hardware_access_decisions
                (condominio_id, device_id, event_id, external_event_id, granted, reason, credential_hash)
                VALUES (%s,%s::uuid,%s,%s,%s,%s,%s)""",
                (event.tenant_id, event.device_id, internal_event_id, event.event_id,
                 granted, reason, credential_hash))

    def device_is_online(self, tenant_id: int, device_id: str, stale_seconds: int = 90) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("""SELECT COALESCE(ultimo_heartbeat_em >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second'), FALSE) AS online
                           FROM hardware_devices WHERE condominio_id=%s AND id=%s::uuid AND ativo""",
                        (stale_seconds, tenant_id, device_id))
            row = cur.fetchone()
            return bool(row and row["online"])

    def recover_stuck_commands(self, stale_seconds: int = 120):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_commands
                           SET status=CASE WHEN tentativas >= max_tentativas THEN 'expired' ELSE 'failed' END,
                               erro='processing_timeout',
                               proxima_tentativa_em=CASE WHEN tentativas >= max_tentativas THEN NULL ELSE CURRENT_TIMESTAMP END,
                               atualizado_em=CURRENT_TIMESTAMP
                           WHERE status='processing'
                             AND atualizado_em < CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')""", (stale_seconds,))
            return cur.rowcount

    def expire_commands(self):
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE hardware_commands SET status='expired', atualizado_em=CURRENT_TIMESTAMP
                           WHERE status IN ('pending','failed')
                             AND ((expira_em IS NOT NULL AND expira_em <= CURRENT_TIMESTAMP)
                                  OR tentativas >= max_tentativas)""")
            return cur.rowcount

    def claim_pending_commands(self, limit: int = 20):
        with self.conn.cursor() as cur:
            cur.execute("""WITH claimed AS (
                    SELECT id FROM hardware_commands
                    WHERE status IN ('pending','failed')
                      AND tentativas < max_tentativas
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
