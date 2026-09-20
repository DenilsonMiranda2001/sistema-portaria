BEGIN;

-- Rate-limit records are short-lived operational security data.
DELETE FROM login_attempts
WHERE janela_inicio < CURRENT_TIMESTAMP - INTERVAL '2 days';

COMMIT;
