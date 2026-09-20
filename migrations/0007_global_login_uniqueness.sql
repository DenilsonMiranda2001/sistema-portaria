BEGIN;

-- Login is intentionally global because the login screen does not ask for a tenant.
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_login_global
    ON usuarios (usuario);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_admins_login_global
    ON platform_admins (usuario);

COMMIT;
