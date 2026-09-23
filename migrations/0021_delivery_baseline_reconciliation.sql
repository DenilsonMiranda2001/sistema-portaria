-- Reconcile fresh baseline delivery schema with installations upgraded through 0019.
-- Historical migration 0019 is immutable because existing installations store its checksum.
ALTER TABLE entregadores DROP CONSTRAINT IF EXISTS ck_entregadores_nome;
ALTER TABLE entregadores ADD CONSTRAINT ck_entregadores_nome
    CHECK (NULLIF(BTRIM(nome), '') IS NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entregadores_id_tenant ON entregadores(id, condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entregadores_tenant_documento
    ON entregadores(condominio_id, documento)
    WHERE documento IS NOT NULL AND NULLIF(BTRIM(documento), '') IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entregadores_tenant_ativos_nome ON entregadores(condominio_id, ativo, nome);
ALTER TABLE lotes_encomendas DROP CONSTRAINT IF EXISTS fk_lotes_entregador_tenant;
ALTER TABLE lotes_encomendas ADD CONSTRAINT fk_lotes_entregador_tenant
    FOREIGN KEY (entregador_id, condominio_id) REFERENCES entregadores(id, condominio_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY IMMEDIATE;
CREATE INDEX IF NOT EXISTS idx_lotes_tenant_entregador_data
    ON lotes_encomendas(condominio_id, entregador_id, data_chegada DESC)
    WHERE entregador_id IS NOT NULL;
