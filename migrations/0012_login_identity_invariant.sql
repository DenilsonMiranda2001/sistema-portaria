BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM usuarios u
        JOIN platform_admins p ON p.usuario = u.usuario
    ) THEN
        RAISE EXCEPTION 'Invariant violation: a login exists in both usuarios and platform_admins';
    END IF;

    IF EXISTS (
        SELECT usuario FROM usuarios GROUP BY usuario HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Invariant violation: duplicate tenant login exists';
    END IF;

    IF EXISTS (
        SELECT usuario FROM platform_admins GROUP BY usuario HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Invariant violation: duplicate platform login exists';
    END IF;
END $$;

COMMIT;
