BEGIN;

-- Enforce tenant ownership only after the bootstrap/backfill migration.
ALTER TABLE usuarios ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE unidades ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE moradores ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE visitantes ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE visitas ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE lotes_encomendas ALTER COLUMN condominio_id SET NOT NULL;
ALTER TABLE encomendas ALTER COLUMN condominio_id SET NOT NULL;

-- Remove legacy global uniqueness so separate condominiums can own equivalent identifiers.
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_usuario_key;
ALTER TABLE unidades DROP CONSTRAINT IF EXISTS unidades_codigo_key;
ALTER TABLE moradores DROP CONSTRAINT IF EXISTS moradores_cpf_key;
ALTER TABLE visitantes DROP CONSTRAINT IF EXISTS visitantes_cpf_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_tenant_usuario ON usuarios(condominio_id, usuario);
CREATE UNIQUE INDEX IF NOT EXISTS uq_unidades_tenant_codigo ON unidades(condominio_id, codigo);
CREATE UNIQUE INDEX IF NOT EXISTS uq_moradores_tenant_cpf ON moradores(condominio_id, cpf) WHERE cpf IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_visitantes_tenant_cpf ON visitantes(condominio_id, cpf);

COMMIT;
