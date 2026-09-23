-- Tenant RBAC v2. The platform control plane remains in platform_admins.
-- A single transaction ensures legacy values are converted before the new constraint is validated.
BEGIN;

ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_nivel_check;

UPDATE usuarios SET nivel = 'admin_condominio' WHERE nivel = 'admin';
UPDATE usuarios SET nivel = 'porteiro' WHERE nivel = 'funcionario';

-- Fail the migration if unexpected legacy roles exist instead of silently mapping them.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM usuarios
        WHERE nivel NOT IN ('admin_condominio', 'administrativo', 'porteiro')
    ) THEN
        RAISE EXCEPTION 'Unexpected tenant role found in usuarios; inspect before applying RBAC migration';
    END IF;
END $$;

ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_nivel_check
    CHECK (nivel IN ('admin_condominio', 'administrativo', 'porteiro'));

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant_role_active
    ON usuarios(condominio_id, nivel, ativo);

COMMIT;
