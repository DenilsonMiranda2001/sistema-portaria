BEGIN;

-- Fast tenant-scoped operational reads.
CREATE INDEX IF NOT EXISTS idx_visitas_tenant_abertas
    ON visitas(condominio_id, data_entrada)
    WHERE data_saida IS NULL;

CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_custodia
    ON encomendas(condominio_id, data_chegada)
    WHERE status = 'retida_portaria';

CREATE INDEX IF NOT EXISTS idx_moradores_tenant_ativos_unidade
    ON moradores(condominio_id, unidade_id, nome)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_visitantes_tenant_nome
    ON visitantes(condominio_id, nome);

-- Database-level guarantee: one visitor cannot have two simultaneous open visits
-- inside the same condominium, even under concurrent requests.
CREATE UNIQUE INDEX IF NOT EXISTS uq_visita_aberta_visitante_tenant
    ON visitas(condominio_id, visitante_id)
    WHERE data_saida IS NULL;

COMMIT;
