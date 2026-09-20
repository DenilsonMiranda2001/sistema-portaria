BEGIN;

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS actor_tipo VARCHAR(30),
    ADD COLUMN IF NOT EXISTS actor_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_audit_actor_time
    ON audit_logs(actor_tipo, actor_id, criado_em DESC);

COMMIT;
