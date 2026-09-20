-- 0001_multi_tenant_foundation.sql
-- Forward-only migration for development databases created before tenant support.
BEGIN;

CREATE TABLE IF NOT EXISTS condominios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(180) NOT NULL,
    slug VARCHAR(120) UNIQUE NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE unidades ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE moradores ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE visitantes ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE visitas ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE lotes_encomendas ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;
ALTER TABLE encomendas ADD COLUMN IF NOT EXISTS condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT;

-- New development environment: create one explicit tenant for bootstrap.
-- Existing environments remain nullable until data is mapped deliberately.
INSERT INTO condominios (nome, slug)
SELECT 'Condomínio Inicial', 'condominio-inicial'
WHERE NOT EXISTS (SELECT 1 FROM condominios);

UPDATE usuarios SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE unidades SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE moradores SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE visitantes SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE visitas SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE lotes_encomendas SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;
UPDATE encomendas SET condominio_id = (SELECT id FROM condominios ORDER BY id LIMIT 1) WHERE condominio_id IS NULL;

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    acao VARCHAR(100) NOT NULL,
    entidade VARCHAR(80),
    entidade_id VARCHAR(80),
    detalhes JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_hash VARCHAR(64),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant ON usuarios(condominio_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_tenant_usuario ON usuarios(condominio_id, usuario) WHERE condominio_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_unidades_tenant ON unidades(condominio_id);
CREATE INDEX IF NOT EXISTS idx_moradores_tenant ON moradores(condominio_id);
CREATE INDEX IF NOT EXISTS idx_visitantes_tenant ON visitantes(condominio_id);
CREATE INDEX IF NOT EXISTS idx_visitas_tenant_data ON visitas(condominio_id, data_entrada DESC);
CREATE INDEX IF NOT EXISTS idx_lotes_tenant_data ON lotes_encomendas(condominio_id, data_chegada DESC);
CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_data ON encomendas(condominio_id, data_chegada DESC);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_logs(condominio_id, criado_em DESC);

COMMIT;
