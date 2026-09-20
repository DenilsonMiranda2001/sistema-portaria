BEGIN;

CREATE OR REPLACE FUNCTION enforce_cross_table_login_uniqueness()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_login text;
BEGIN
    normalized_login := NEW.usuario;

    -- Serialize identity claims for the same login even across different tables.
    PERFORM pg_advisory_xact_lock(hashtextextended(normalized_login, 19052026));

    IF TG_TABLE_NAME = 'usuarios' THEN
        IF EXISTS (SELECT 1 FROM platform_admins WHERE usuario = normalized_login) THEN
            RAISE EXCEPTION 'login already exists in platform_admins' USING ERRCODE = '23505';
        END IF;
    ELSIF TG_TABLE_NAME = 'platform_admins' THEN
        IF EXISTS (SELECT 1 FROM usuarios WHERE usuario = normalized_login) THEN
            RAISE EXCEPTION 'login already exists in usuarios' USING ERRCODE = '23505';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_usuarios_cross_login_unique ON usuarios;
CREATE TRIGGER trg_usuarios_cross_login_unique
BEFORE INSERT OR UPDATE OF usuario ON usuarios
FOR EACH ROW EXECUTE FUNCTION enforce_cross_table_login_uniqueness();

DROP TRIGGER IF EXISTS trg_platform_admins_cross_login_unique ON platform_admins;
CREATE TRIGGER trg_platform_admins_cross_login_unique
BEFORE INSERT OR UPDATE OF usuario ON platform_admins
FOR EACH ROW EXECUTE FUNCTION enforce_cross_table_login_uniqueness();

COMMIT;
