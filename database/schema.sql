-- ============================================================
-- PORTARIA CONTROL — Schema PostgreSQL
-- ============================================================

-- USUÁRIOS DO SISTEMA
CREATE TABLE IF NOT EXISTS usuarios (
    id         SERIAL PRIMARY KEY,
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
    codigo     VARCHAR(50)   UNIQUE NOT NULL,
    descricao  VARCHAR(150),
    ativo      BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- MORADORES
CREATE TABLE IF NOT EXISTS moradores (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(150)  NOT NULL,
    cpf         VARCHAR(11)   UNIQUE,
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
    nome       VARCHAR(150)  NOT NULL,
    cpf        VARCHAR(11)   UNIQUE NOT NULL,
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
