import logging
from pathlib import Path
from database.connection import conectar, liberar
from werkzeug.security import generate_password_hash, check_password_hash
from utils.validators import limpar_cpf

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# INICIALIZAÇÃO
# ──────────────────────────────────────────────────────────────

def criar_tabelas():
    conn = None
    try:
        conn = conectar()
        with conn.cursor() as cur:
            sql = (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")
            cur.execute(sql)

            # Migrações — adicionam colunas que podem não existir em bancos antigos
            migracoes = [
                "ALTER TABLE usuarios  ADD COLUMN IF NOT EXISTS ativo      BOOLEAN NOT NULL DEFAULT TRUE",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS unidade_id INTEGER REFERENCES unidades(id) ON DELETE SET NULL",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS morador_id INTEGER REFERENCES moradores(id) ON DELETE SET NULL",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS placa      VARCHAR(20)",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS marca      VARCHAR(100)",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS modelo     VARCHAR(100)",
                "ALTER TABLE visitas   ADD COLUMN IF NOT EXISTS observacao TEXT",
            ]
            for m in migracoes:
                try:
                    cur.execute(m)
                except Exception as e:
                    logger.warning("Migração ignorada: %s — %s", m[:60], e)
                    conn.rollback()
                    # Reabre cursor após rollback parcial
                    cur = conn.cursor()

            # Índices para as novas colunas (idempotentes)
            indices_extra = [
                "CREATE INDEX IF NOT EXISTS idx_visitas_unidade  ON visitas(unidade_id)",
                "CREATE INDEX IF NOT EXISTS idx_visitas_morador  ON visitas(morador_id)",
            ]
            for idx in indices_extra:
                try:
                    cur.execute(idx)
                except Exception as e:
                    logger.warning("Índice ignorado: %s — %s", idx[:60], e)

        conn.commit()
        logger.info("Tabelas criadas/atualizadas com sucesso.")
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("Erro ao criar tabelas")
    finally:
        if conn:
            liberar(conn)


# ──────────────────────────────────────────────────────────────
# USUÁRIOS
# ──────────────────────────────────────────────────────────────

def criar_usuario(nome, usuario, senha, nivel):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (nome, usuario, senha, nivel, ativo)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                (nome or "").strip().upper(),
                (usuario or "").strip(),
                generate_password_hash(senha),
                (nivel or "funcionario").strip().lower(),
            ))
            novo = cur.fetchone()
        conn.commit()
        logger.info("Usuário criado: %s", usuario)
        return novo
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def listar_usuarios():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, usuario, nivel, ativo, criado_em FROM usuarios ORDER BY nome")
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_usuario_por_id(usuario_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, usuario, nivel, ativo, criado_em FROM usuarios WHERE id = %s",
                (usuario_id,)
            )
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_usuario(usuario):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, usuario, senha, nivel, ativo FROM usuarios WHERE usuario = %s",
                ((usuario or "").strip(),)
            )
            return cur.fetchone()
    finally:
        liberar(conn)


def verificar_senha(usuario_banco, senha_digitada):
    if not usuario_banco or not usuario_banco.get("ativo"):
        return False
    return check_password_hash(usuario_banco.get("senha", ""), senha_digitada)


def atualizar_usuario(usuario_id, nome, usuario, nivel):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE usuarios SET nome = %s, usuario = %s, nivel = %s WHERE id = %s
            """, (
                (nome or "").strip().upper(),
                (usuario or "").strip(),
                (nivel or "funcionario").strip().lower(),
                usuario_id,
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_senha_usuario(usuario_id, nova_senha):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET senha = %s WHERE id = %s",
                (generate_password_hash(nova_senha), usuario_id)
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def inativar_usuario(usuario_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (usuario_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def ativar_usuario(usuario_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo = TRUE WHERE id = %s", (usuario_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# UNIDADES
# ──────────────────────────────────────────────────────────────

def listar_unidades():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descricao, ativo FROM unidades WHERE ativo = TRUE ORDER BY codigo")
            return cur.fetchall()
    finally:
        liberar(conn)


def criar_unidade(codigo, descricao=None):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO unidades (codigo, descricao)
                VALUES (%s, %s)
                ON CONFLICT (codigo) DO NOTHING
                RETURNING id
            """, ((codigo or "").strip().upper(), (descricao or "").strip()))
            resultado = cur.fetchone()
        conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_unidade_por_id(unidade_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descricao, ativo FROM unidades WHERE id = %s", (unidade_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# MORADORES
# ──────────────────────────────────────────────────────────────

def cadastrar_morador(nome, cpf, telefone, email, unidade_id, observacao):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO moradores (nome, cpf, telefone, email, unidade_id, observacao, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                (nome or "").strip().upper(),
                limpar_cpf(cpf) or None,
                (telefone or "").strip() or None,
                (email or "").strip().lower() or None,
                unidade_id or None,
                (observacao or "").strip().upper() or None,
            ))
            novo = cur.fetchone()
        conn.commit()
        logger.info("Morador cadastrado: %s", nome)
        return novo["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def listar_moradores(apenas_ativos=True):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            filtro = "WHERE m.ativo = TRUE" if apenas_ativos else ""
            cur.execute(f"""
                SELECT
                    m.id, m.nome, m.cpf, m.telefone, m.email,
                    m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                    m.ativo, m.observacao, m.criado_em
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id
                {filtro}
                ORDER BY m.nome
            """)
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_moradores(termo):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            termo = (termo or "").strip()
            if not termo or len(termo) < 2:
                cur.execute("""
                    SELECT m.id, m.nome, m.cpf, m.telefone, m.email,
                           m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                           m.ativo, m.observacao, m.criado_em
                    FROM moradores m
                    LEFT JOIN unidades u ON u.id = m.unidade_id
                    WHERE m.ativo = TRUE
                    ORDER BY m.nome
                    LIMIT 30
                """)
            else:
                like = f"%{termo}%"
                cur.execute("""
                    SELECT m.id, m.nome, m.cpf, m.telefone, m.email,
                           m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                           m.ativo, m.observacao, m.criado_em
                    FROM moradores m
                    LEFT JOIN unidades u ON u.id = m.unidade_id
                    WHERE m.ativo = TRUE
                      AND (m.nome ILIKE %s OR m.cpf ILIKE %s OR u.codigo ILIKE %s)
                    ORDER BY m.nome
                    LIMIT 30
                """, (like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_morador_por_id(morador_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.nome, m.cpf, m.telefone, m.email,
                       m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                       m.ativo, m.observacao, m.criado_em
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id
                WHERE m.id = %s
            """, (morador_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


def atualizar_morador(morador_id, nome, cpf, telefone, email, unidade_id, observacao):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE moradores
                SET nome = %s, cpf = %s, telefone = %s, email = %s,
                    unidade_id = %s, observacao = %s
                WHERE id = %s
            """, (
                (nome or "").strip().upper(),
                limpar_cpf(cpf) or None,
                (telefone or "").strip() or None,
                (email or "").strip().lower() or None,
                unidade_id or None,
                (observacao or "").strip().upper() or None,
                morador_id,
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def inativar_morador(morador_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE moradores SET ativo = FALSE WHERE id = %s", (morador_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def ativar_morador(morador_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE moradores SET ativo = TRUE WHERE id = %s", (morador_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def cpf_morador_ja_cadastrado(cpf, morador_id=None):
    cpf = limpar_cpf(cpf)
    if not cpf:
        return None
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if morador_id:
                cur.execute(
                    "SELECT id, nome FROM moradores WHERE cpf = %s AND id <> %s LIMIT 1",
                    (cpf, morador_id)
                )
            else:
                cur.execute("SELECT id, nome FROM moradores WHERE cpf = %s LIMIT 1", (cpf,))
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_moradores_ajax(termo):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            like = f"%{(termo or '').strip()}%"
            cur.execute("""
                SELECT m.id, m.nome, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id
                WHERE m.ativo = TRUE
                  AND (m.nome ILIKE %s OR u.codigo ILIKE %s)
                ORDER BY m.nome
                LIMIT 15
            """, (like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def total_moradores():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM moradores WHERE ativo = TRUE")
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# VISITANTES
# ──────────────────────────────────────────────────────────────

def cpf_ja_cadastrado(cpf, visitante_id=None):
    cpf = limpar_cpf(cpf)
    if not cpf:
        return None
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if visitante_id:
                cur.execute(
                    "SELECT id, nome FROM visitantes WHERE cpf = %s AND id <> %s LIMIT 1",
                    (cpf, visitante_id)
                )
            else:
                cur.execute("SELECT id, nome FROM visitantes WHERE cpf = %s LIMIT 1", (cpf,))
            return cur.fetchone()
    finally:
        liberar(conn)


def cadastrar_visitante(nome, cpf, tipo, placa, modelo, marca, foto, observacao):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO visitantes (nome, cpf, tipo, placa, modelo, marca, foto, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                (nome or "").strip().upper(),
                limpar_cpf(cpf),
                (tipo or "").strip().upper(),
                (placa or "").strip().upper(),
                (modelo or "").strip().upper(),
                (marca or "").strip().upper(),
                foto,
                (observacao or "").strip().upper(),
            ))
            novo = cur.fetchone()
        conn.commit()
        return novo["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_visitantes(termo):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            termo = (termo or "").strip()
            if not termo:
                cur.execute("""
                    SELECT v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                           (SELECT vi.endereco FROM visitas vi WHERE vi.visitante_id = v.id
                            ORDER BY vi.data_entrada DESC LIMIT 1) AS ultimo_endereco
                    FROM visitantes v ORDER BY v.id DESC LIMIT 20
                """)
            else:
                like = f"%{termo}%"
                cur.execute("""
                    SELECT v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                           (SELECT vi.endereco FROM visitas vi WHERE vi.visitante_id = v.id
                            ORDER BY vi.data_entrada DESC LIMIT 1) AS ultimo_endereco
                    FROM visitantes v
                    WHERE v.nome ILIKE %s OR v.cpf ILIKE %s OR v.placa ILIKE %s
                    ORDER BY v.id DESC LIMIT 20
                """, (like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_um_por_cpf(cpf):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes WHERE cpf = %s LIMIT 1
            """, (limpar_cpf(cpf),))
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_visitante_por_id(visitante_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes WHERE id = %s
            """, (visitante_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


def listar_visitantes_paginado(pagina=1, por_pagina=20):
    conn = conectar()
    offset = (pagina - 1) * por_pagina
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes ORDER BY id DESC LIMIT %s OFFSET %s
            """, (por_pagina, offset))
            visitantes = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM visitantes")
            total = cur.fetchone()["total"]
        return visitantes, total
    finally:
        liberar(conn)


def atualizar_visitante(visitante_id, nome, cpf, tipo, placa, modelo, marca, foto, observacao):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if foto:
                cur.execute("""
                    UPDATE visitantes
                    SET nome=%s, cpf=%s, tipo=%s, placa=%s, modelo=%s, marca=%s, foto=%s, observacao=%s
                    WHERE id=%s
                """, (
                    (nome or "").strip().upper(), limpar_cpf(cpf),
                    (tipo or "").strip().upper(), (placa or "").strip().upper(),
                    (modelo or "").strip().upper(), (marca or "").strip().upper(),
                    foto, (observacao or "").strip().upper(), visitante_id,
                ))
            else:
                cur.execute("""
                    UPDATE visitantes
                    SET nome=%s, cpf=%s, tipo=%s, placa=%s, modelo=%s, marca=%s, observacao=%s
                    WHERE id=%s
                """, (
                    (nome or "").strip().upper(), limpar_cpf(cpf),
                    (tipo or "").strip().upper(), (placa or "").strip().upper(),
                    (modelo or "").strip().upper(), (marca or "").strip().upper(),
                    (observacao or "").strip().upper(), visitante_id,
                ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def remover_visitante(visitante_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM visitantes WHERE id = %s", (visitante_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_foto_visitante(visitante_id, nome_arquivo):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE visitantes SET foto = %s WHERE id = %s", (nome_arquivo, visitante_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_observacao_visitante(visitante_id, observacao):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visitantes SET observacao = %s WHERE id = %s",
                ((observacao or "").strip().upper(), visitante_id)
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def listar_cpfs_visitantes():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cpf FROM visitantes")
            return {row["cpf"] for row in cur.fetchall() if row["cpf"]}
    finally:
        liberar(conn)


def importar_visitantes_em_lotes(lista_visitantes, tamanho_lote=100):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO visitantes (nome, cpf, tipo, placa, modelo, marca, foto, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cpf) DO NOTHING
            """
            for i in range(0, len(lista_visitantes), tamanho_lote):
                cur.executemany(query, lista_visitantes[i:i + tamanho_lote])
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# VISITAS / ENTRADAS E SAÍDAS
# ──────────────────────────────────────────────────────────────

def registrar_entrada(visitante_id, endereco, placa=None, marca=None, modelo=None,
                      observacao=None, usuario_id=None, unidade_id=None, morador_id=None):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            # Atualiza dados do veículo no cadastro do visitante
            cur.execute("""
                UPDATE visitantes
                SET placa = COALESCE(NULLIF(%s,''), placa),
                    marca  = COALESCE(NULLIF(%s,''), marca),
                    modelo = COALESCE(NULLIF(%s,''), modelo)
                WHERE id = %s
            """, (
                (placa or "").strip().upper(),
                (marca or "").strip().upper(),
                (modelo or "").strip().upper(),
                visitante_id,
            ))

            cur.execute("""
                INSERT INTO visitas
                    (visitante_id, endereco, placa, marca, modelo, observacao,
                     usuario_entrada_id, unidade_id, morador_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                visitante_id,
                (endereco or "").strip().upper(),
                (placa or "").strip().upper(),
                (marca or "").strip().upper(),
                (modelo or "").strip().upper(),
                (observacao or "").strip().upper(),
                usuario_id,
                unidade_id or None,
                morador_id or None,
            ))
            nova_visita = cur.fetchone()
        conn.commit()
        logger.info("Entrada registrada: visitante=%s visita=%s", visitante_id, nova_visita["id"])
        return nova_visita["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def registrar_saida(visitante_id, usuario_saida_id=None):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE visitas
                SET data_saida = CURRENT_TIMESTAMP, usuario_saida_id = %s
                WHERE id = (
                    SELECT id FROM visitas
                    WHERE visitante_id = %s AND data_saida IS NULL
                    ORDER BY data_entrada DESC LIMIT 1
                )
            """, (usuario_saida_id, visitante_id))
        conn.commit()
        logger.info("Saída registrada: visitante=%s", visitante_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def visitantes_ativos():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                    vi.id AS visita_id, vi.endereco, vi.data_entrada,
                    m.nome AS morador_nome, u.codigo AS unidade_codigo
                FROM visitantes v
                INNER JOIN visitas vi ON v.id = vi.visitante_id AND vi.data_saida IS NULL
                LEFT JOIN moradores m ON m.id = vi.morador_id
                LEFT JOIN unidades u ON u.id = vi.unidade_id
                ORDER BY vi.data_entrada DESC
            """)
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_ativos(termo):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            like = f"%{(termo or '').strip()}%"
            cur.execute("""
                SELECT
                    v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                    vi.id AS visita_id, vi.endereco, vi.data_entrada,
                    m.nome AS morador_nome, u.codigo AS unidade_codigo
                FROM visitantes v
                INNER JOIN visitas vi ON v.id = vi.visitante_id AND vi.data_saida IS NULL
                LEFT JOIN moradores m ON m.id = vi.morador_id
                LEFT JOIN unidades u ON u.id = vi.unidade_id
                WHERE v.nome ILIKE %s OR v.cpf ILIKE %s OR v.placa ILIKE %s OR vi.endereco ILIKE %s
                ORDER BY vi.data_entrada DESC
            """, (like, like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def historico_visitante(visitante_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    vi.id, vi.visitante_id, vi.endereco,
                    vi.data_entrada, vi.data_saida,
                    ue.nome AS autorizado_por,
                    us.nome AS saida_registrada_por,
                    m.nome AS morador_nome,
                    u.codigo AS unidade_codigo
                FROM visitas vi
                LEFT JOIN usuarios ue ON vi.usuario_entrada_id = ue.id
                LEFT JOIN usuarios us ON vi.usuario_saida_id = us.id
                LEFT JOIN moradores m ON vi.morador_id = m.id
                LEFT JOIN unidades u ON vi.unidade_id = u.id
                WHERE vi.visitante_id = %s
                ORDER BY vi.data_entrada DESC
            """, (visitante_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def atualizar_visita_ativa(visitante_id, endereco):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE visitas SET endereco = %s
                WHERE id = (
                    SELECT id FROM visitas
                    WHERE visitante_id = %s AND data_saida IS NULL
                    ORDER BY data_entrada DESC LIMIT 1
                )
            """, ((endereco or "").strip().upper(), visitante_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────

def total_visitantes_cadastrados():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitantes")
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_visitantes_ativos():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE data_saida IS NULL")
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_entradas_hoje():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE DATE(data_entrada) = CURRENT_DATE")
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_saidas_hoje():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE DATE(data_saida) = CURRENT_DATE")
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def ultima_entrada():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.nome, vi.data_entrada
                FROM visitas vi
                JOIN visitantes v ON v.id = vi.visitante_id
                ORDER BY vi.data_entrada DESC LIMIT 1
            """)
            r = cur.fetchone()
            if not r:
                return ("-", "-")
            return r["nome"], r["data_entrada"].strftime("%H:%M") if r["data_entrada"] else "-"
    finally:
        liberar(conn)


def ultimas_entradas_dashboard(limite=5):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.nome, v.foto, vi.endereco, vi.data_entrada,
                       m.nome AS morador_nome, u.codigo AS unidade_codigo
                FROM visitas vi
                JOIN visitantes v ON v.id = vi.visitante_id
                LEFT JOIN moradores m ON vi.morador_id = m.id
                LEFT JOIN unidades u ON vi.unidade_id = u.id
                ORDER BY vi.data_entrada DESC LIMIT %s
            """, (limite,))
            return cur.fetchall()
    finally:
        liberar(conn)
