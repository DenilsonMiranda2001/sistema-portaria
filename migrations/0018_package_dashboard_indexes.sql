BEGIN;

-- Supports tenant-scoped package dashboard counters and historical views
-- without forcing casts over timestamp columns.
CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_retirada
    ON encomendas(condominio_id, data_retirada DESC)
    WHERE data_retirada IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_atualizado_final
    ON encomendas(condominio_id, atualizado_em DESC)
    WHERE status IN ('retirada', 'cancelada');

COMMIT;
