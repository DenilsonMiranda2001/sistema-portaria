BEGIN;

CREATE TABLE IF NOT EXISTS login_attempts (
    chave VARCHAR(64) PRIMARY KEY,
    tentativas INTEGER NOT NULL DEFAULT 0,
    janela_inicio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueado_ate TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_cleanup
    ON login_attempts(janela_inicio);

COMMIT;
