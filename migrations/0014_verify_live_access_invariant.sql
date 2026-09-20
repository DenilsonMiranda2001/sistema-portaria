BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM visitas
        WHERE data_saida IS NULL
        GROUP BY condominio_id, visitante_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Invariant violation: duplicate open visits exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND indexname = 'uq_visita_aberta_visitante_tenant'
    ) THEN
        RAISE EXCEPTION 'Invariant violation: live access unique index is missing';
    END IF;
END $$;

COMMIT;
