BEGIN;

CREATE TABLE entregadores (
    id BIGSERIAL PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    nome VARCHAR(150) NOT NULL,
    documento VARCHAR(50),
    telefone VARCHAR(30),
    transportadora VARCHAR(80),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_entregadores_nome CHECK (NULLIF(BTRIM(nome), '') IS NOT NULL)
);

CREATE UNIQUE INDEX uq_entregadores_id_tenant ON entregadores(id, condominio_id);
CREATE UNIQUE INDEX uq_entregadores_tenant_documento
    ON entregadores(condominio_id, documento)
    WHERE documento IS NOT NULL AND NULLIF(BTRIM(documento), '') IS NOT NULL;
CREATE INDEX idx_entregadores_tenant_ativos_nome
    ON entregadores(condominio_id, ativo, nome);

ALTER TABLE lotes_encomendas ADD COLUMN entregador_id BIGINT;

ALTER TABLE lotes_encomendas
    ADD CONSTRAINT fk_lotes_entregador_tenant
    FOREIGN KEY (entregador_id, condominio_id)
    REFERENCES entregadores(id, condominio_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY IMMEDIATE;

CREATE INDEX idx_lotes_tenant_entregador_data
    ON lotes_encomendas(condominio_id, entregador_id, data_chegada DESC)
    WHERE entregador_id IS NOT NULL;

COMMIT;
