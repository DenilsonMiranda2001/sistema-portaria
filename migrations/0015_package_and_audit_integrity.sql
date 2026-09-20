BEGIN;

ALTER TABLE encomendas
    DROP CONSTRAINT IF EXISTS ck_encomendas_status_known;
ALTER TABLE encomendas
    ADD CONSTRAINT ck_encomendas_status_known
    CHECK (status IN ('recebida','aguardando_resposta','morador_em_casa','retida_portaria','retirada','entregue_na_porta','cancelada'))
    NOT VALID;

ALTER TABLE encomendas
    DROP CONSTRAINT IF EXISTS ck_encomendas_retirada_evidence;
ALTER TABLE encomendas
    ADD CONSTRAINT ck_encomendas_retirada_evidence
    CHECK (
        status <> 'retirada'
        OR (data_retirada IS NOT NULL AND NULLIF(BTRIM(retirado_por), '') IS NOT NULL)
    )
    NOT VALID;

CREATE INDEX IF NOT EXISTS idx_audit_tenant_action_time
    ON audit_logs(condominio_id, acao, criado_em DESC);

COMMIT;
