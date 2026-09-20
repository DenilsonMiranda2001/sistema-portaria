BEGIN;

-- A visitor may have at most one open visit inside a tenant.
CREATE UNIQUE INDEX IF NOT EXISTS uq_visitas_tenant_visitante_ativa
    ON visitas(condominio_id, visitante_id)
    WHERE data_saida IS NULL;

-- Strengthen the most common tenant-first access paths.
CREATE INDEX IF NOT EXISTS idx_visitantes_tenant_nome
    ON visitantes(condominio_id, UPPER(nome));
CREATE INDEX IF NOT EXISTS idx_moradores_tenant_nome
    ON moradores(condominio_id, UPPER(nome));
CREATE INDEX IF NOT EXISTS idx_lotes_tenant_data
    ON lotes_encomendas(condominio_id, data_chegada DESC);
CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_status
    ON encomendas(condominio_id, status);

COMMIT;
