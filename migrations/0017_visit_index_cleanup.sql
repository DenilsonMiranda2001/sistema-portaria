BEGIN;

-- 0013/0014 established and verified uq_visita_aberta_visitante_tenant.
-- Remove the older equivalent index to avoid duplicate write amplification.
DROP INDEX IF EXISTS uq_visitas_tenant_visitante_ativa;

-- Supports tenant-scoped daily exit counters and recent-exit queries.
CREATE INDEX IF NOT EXISTS idx_visitas_tenant_saida
    ON visitas(condominio_id, data_saida DESC)
    WHERE data_saida IS NOT NULL;

COMMIT;
