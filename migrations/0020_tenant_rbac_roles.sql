-- Tenant RBAC v2: platform admin remains isolated in platform_admins.
-- Tenant users gain explicit condominium roles.
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_nivel_check;

UPDATE usuarios SET nivel = 'admin_condominio' WHERE nivel = 'admin';
UPDATE usuarios SET nivel = 'porteiro' WHERE nivel = 'funcionario';

ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_nivel_check
    CHECK (nivel IN ('admin_condominio', 'administrativo', 'porteiro'));

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant_role_active
    ON usuarios(condominio_id, nivel, ativo);
