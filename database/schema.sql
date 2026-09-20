-- ============================================================
-- PORTARIA CONTROL — Schema PostgreSQL
-- ============================================================

-- CONDOMÍNIOS / TENANTS
CREATE TABLE IF NOT EXISTS condominios (
    id         SERIAL PRIMARY KEY,
    nome       VARCHAR(180) NOT NULL,
    slug       VARCHAR(120) UNIQUE NOT NULL,
    ativo      BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- USUÁRIOS DO SISTEMA
CREATE TABLE IF NOT EXISTS usuarios (
    id         SERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    nome       VARCHAR(150)  NOT NULL,
    usuario    VARCHAR(100)  UNIQUE NOT NULL,
    senha      VARCHAR(255)  NOT NULL,
    nivel      VARCHAR(20)   NOT NULL CHECK (nivel IN ('admin', 'funcionario')),
    ativo      BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- UNIDADES / CASAS / LOTES
CREATE TABLE IF NOT EXISTS unidades (
    id         SERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    codigo     VARCHAR(50)   NOT NULL,
    descricao  VARCHAR(150),
    ativo      BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- MORADORES
CREATE TABLE IF NOT EXISTS moradores (
    id          SERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    nome        VARCHAR(150)  NOT NULL,
    cpf         VARCHAR(11),
    telefone    VARCHAR(20),
    email       VARCHAR(150),
    unidade_id  INTEGER       REFERENCES unidades(id) ON DELETE SET NULL,
    ativo       BOOLEAN       NOT NULL DEFAULT TRUE,
    observacao  TEXT,
    criado_em   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- VISITANTES
CREATE TABLE IF NOT EXISTS visitantes (
    id         SERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    nome       VARCHAR(150)  NOT NULL,
    cpf        VARCHAR(11)   NOT NULL,
    tipo       VARCHAR(50),
    placa      VARCHAR(20),
    modelo     VARCHAR(100),
    marca      VARCHAR(100),
    foto       VARCHAR(255),
    observacao TEXT,
    criado_em  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- VISITAS / ENTRADAS E SAÍDAS
CREATE TABLE IF NOT EXISTS visitas (
    id                 SERIAL PRIMARY KEY,
    condominio_id      INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    visitante_id       INTEGER      NOT NULL REFERENCES visitantes(id) ON DELETE CASCADE,
    unidade_id         INTEGER      REFERENCES unidades(id) ON DELETE SET NULL,
    morador_id         INTEGER      REFERENCES moradores(id) ON DELETE SET NULL,
    endereco           VARCHAR(255) NOT NULL,
    placa              VARCHAR(20),
    marca              VARCHAR(100),
    modelo             VARCHAR(100),
    observacao         TEXT,
    data_entrada       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_saida         TIMESTAMP,
    usuario_entrada_id INTEGER      REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_saida_id   INTEGER      REFERENCES usuarios(id) ON DELETE SET NULL
);

-- LOTES DE ENCOMENDAS
CREATE TABLE IF NOT EXISTS lotes_encomendas (
    id                SERIAL PRIMARY KEY,
    condominio_id     INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    nome_entregador   VARCHAR(150),
    transportadora    VARCHAR(50)  NOT NULL,
    observacao        TEXT,
    data_chegada      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status            VARCHAR(20)  NOT NULL DEFAULT 'aberto'
                      CHECK (status IN ('aberto', 'em_triagem', 'concluido', 'cancelado')),
    usuario_criacao_id INTEGER      REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_em         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ENCOMENDAS INDIVIDUAIS
CREATE TABLE IF NOT EXISTS encomendas (
    id                SERIAL PRIMARY KEY,
    condominio_id     INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    lote_id           INTEGER      NOT NULL REFERENCES lotes_encomendas(id) ON DELETE RESTRICT,
    morador_id        INTEGER      REFERENCES moradores(id) ON DELETE SET NULL,
    unidade_id        INTEGER      REFERENCES unidades(id) ON DELETE SET NULL,
    nome_morador      VARCHAR(150),
    unidade           VARCHAR(50)  NOT NULL,
    codigo_rastreio   VARCHAR(150),
    descricao         VARCHAR(255),
    status            VARCHAR(30)  NOT NULL DEFAULT 'recebida'
                      CHECK (status IN (
                          'recebida', 'aguardando_resposta', 'morador_em_casa',
                          'retida_portaria', 'entregue_na_porta', 'retirada', 'cancelada'
                      )),
    codigo_retirada   VARCHAR(20)  UNIQUE NOT NULL,
    data_chegada      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_resposta     TIMESTAMP,
    data_retirada     TIMESTAMP,
    retirado_por      VARCHAR(150),
    observacao        TEXT,
    usuario_criacao_id INTEGER     REFERENCES usuarios(id) ON DELETE SET NULL,
    atualizado_em     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- AUDITORIA
CREATE TABLE IF NOT EXISTS audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    condominio_id INTEGER REFERENCES condominios(id) ON DELETE RESTRICT,
    usuario_id    INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    acao          VARCHAR(100) NOT NULL,
    entidade      VARCHAR(80),
    entidade_id   VARCHAR(80),
    detalhes      JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_hash       VARCHAR(64),
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tenant-aware uniqueness. These indexes allow the same CPF/unit in distinct condominiums.
CREATE UNIQUE INDEX IF NOT EXISTS uq_unidades_tenant_codigo ON unidades(condominio_id, codigo) WHERE condominio_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_moradores_tenant_cpf ON moradores(condominio_id, cpf) WHERE condominio_id IS NOT NULL AND cpf IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_visitantes_tenant_cpf ON visitantes(condominio_id, cpf) WHERE condominio_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_logs(condominio_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_usuarios_tenant ON usuarios(condominio_id);
CREATE INDEX IF NOT EXISTS idx_visitas_tenant_data ON visitas(condominio_id, data_entrada DESC);
CREATE INDEX IF NOT EXISTS idx_encomendas_tenant_data ON encomendas(condominio_id, data_chegada DESC);

-- ÍNDICES DE PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_visitantes_cpf        ON visitantes(cpf);
CREATE INDEX IF NOT EXISTS idx_visitantes_nome       ON visitantes(UPPER(nome));
CREATE INDEX IF NOT EXISTS idx_visitantes_placa      ON visitantes(placa);
CREATE INDEX IF NOT EXISTS idx_moradores_cpf         ON moradores(cpf);
CREATE INDEX IF NOT EXISTS idx_moradores_nome        ON moradores(UPPER(nome));
CREATE INDEX IF NOT EXISTS idx_moradores_unidade     ON moradores(unidade_id);
CREATE INDEX IF NOT EXISTS idx_visitas_visitante     ON visitas(visitante_id);
CREATE INDEX IF NOT EXISTS idx_visitas_data_entrada  ON visitas(data_entrada);
CREATE INDEX IF NOT EXISTS idx_visitas_sem_saida     ON visitas(visitante_id) WHERE data_saida IS NULL;
CREATE INDEX IF NOT EXISTS idx_lotes_encomendas_data ON lotes_encomendas(data_chegada);
CREATE INDEX IF NOT EXISTS idx_lotes_encomendas_status ON lotes_encomendas(status);
CREATE INDEX IF NOT EXISTS idx_encomendas_lote       ON encomendas(lote_id);
CREATE INDEX IF NOT EXISTS idx_encomendas_status     ON encomendas(status);
CREATE INDEX IF NOT EXISTS idx_encomendas_data       ON encomendas(data_chegada);
CREATE INDEX IF NOT EXISTS idx_encomendas_unidade    ON encomendas(UPPER(unidade));
CREATE INDEX IF NOT EXISTS idx_encomendas_codigo     ON encomendas(UPPER(codigo_retirada));
