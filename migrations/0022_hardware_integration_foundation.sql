-- Vendor-neutral hardware integration foundation.
-- No physical device is contacted by this migration.
CREATE TABLE IF NOT EXISTS hardware_devices (
    id UUID PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    vendor VARCHAR(50) NOT NULL,
    external_device_id VARCHAR(150) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    configuracao JSONB NOT NULL DEFAULT '{}'::jsonb,
    ultimo_heartbeat_em TIMESTAMPTZ,
    auth_key_id VARCHAR(80),
    auth_secret_hash VARCHAR(64),
    auth_secret_rotated_em TIMESTAMPTZ,
    auth_revoked_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (condominio_id, vendor, external_device_id)
);

CREATE TABLE IF NOT EXISTS hardware_credentials (
    id UUID PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    tipo VARCHAR(40) NOT NULL,
    identificador_hash VARCHAR(64) NOT NULL,
    morador_id INTEGER REFERENCES moradores(id) ON DELETE SET NULL,
    visitante_id INTEGER REFERENCES visitantes(id) ON DELETE SET NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (condominio_id, tipo, identificador_hash)
);

CREATE TABLE IF NOT EXISTS hardware_events (
    id BIGSERIAL PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    device_id UUID NOT NULL REFERENCES hardware_devices(id) ON DELETE RESTRICT,
    external_event_id VARCHAR(180) NOT NULL,
    tipo VARCHAR(60) NOT NULL,
    credential_hash VARCHAR(64),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ocorrido_em TIMESTAMPTZ NOT NULL,
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (condominio_id, device_id, external_event_id)
);

CREATE TABLE IF NOT EXISTS hardware_commands (
    id UUID PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    device_id UUID NOT NULL REFERENCES hardware_devices(id) ON DELETE RESTRICT,
    tipo VARCHAR(60) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','succeeded','failed','expired')),
    tentativas INTEGER NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
    max_tentativas INTEGER NOT NULL DEFAULT 5 CHECK (max_tentativas BETWEEN 1 AND 20),
    proxima_tentativa_em TIMESTAMPTZ,
    erro TEXT,
    expira_em TIMESTAMPTZ,
    concluido_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hw_devices_tenant_active ON hardware_devices(condominio_id, ativo);
CREATE UNIQUE INDEX IF NOT EXISTS uq_hw_devices_auth_key ON hardware_devices(auth_key_id) WHERE auth_key_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS hardware_auth_nonces (
    device_id UUID NOT NULL REFERENCES hardware_devices(id) ON DELETE CASCADE,
    nonce_hash VARCHAR(64) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_em TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (device_id, nonce_hash)
);
CREATE INDEX IF NOT EXISTS idx_hw_auth_nonces_expiry ON hardware_auth_nonces(expira_em);
CREATE INDEX IF NOT EXISTS idx_hw_events_tenant_time ON hardware_events(condominio_id, ocorrido_em DESC);
CREATE INDEX IF NOT EXISTS idx_hw_commands_pending ON hardware_commands(status, proxima_tentativa_em) WHERE status IN ('pending','failed');
CREATE TABLE IF NOT EXISTS hardware_access_policies (
    id UUID PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    credential_id UUID NOT NULL REFERENCES hardware_credentials(id) ON DELETE CASCADE,
    device_id UUID REFERENCES hardware_devices(id) ON DELETE CASCADE,
    zona VARCHAR(80),
    valido_de TIMESTAMPTZ,
    valido_ate TIMESTAMPTZ,
    dias_semana SMALLINT[] NOT NULL DEFAULT ARRAY[0,1,2,3,4,5,6],
    hora_inicio TIME,
    hora_fim TIME,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (valido_ate IS NULL OR valido_de IS NULL OR valido_ate > valido_de),
    CHECK (hora_fim IS NULL OR hora_inicio IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_hw_policy_tenant_credential ON hardware_access_policies(condominio_id, credential_id) WHERE ativo;
CREATE INDEX IF NOT EXISTS idx_hw_devices_heartbeat ON hardware_devices(condominio_id, ultimo_heartbeat_em) WHERE ativo;

CREATE TABLE IF NOT EXISTS hardware_access_decisions (
    id BIGSERIAL PRIMARY KEY,
    condominio_id INTEGER NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    device_id UUID NOT NULL REFERENCES hardware_devices(id) ON DELETE RESTRICT,
    event_id BIGINT REFERENCES hardware_events(id) ON DELETE SET NULL,
    external_event_id VARCHAR(180) NOT NULL,
    granted BOOLEAN NOT NULL,
    reason VARCHAR(80) NOT NULL,
    credential_hash VARCHAR(64),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hw_decisions_tenant_time ON hardware_access_decisions(condominio_id, criado_em DESC);
