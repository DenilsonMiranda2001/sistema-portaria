import logging
from pathlib import Path
from database.connection import conectar, liberar


def _tenant_id():
    # Imported lazily so database helpers remain importable in CLI/migration contexts.
    from flask import g, has_request_context
    if not has_request_context():
        return None
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is None:
        raise RuntimeError("Authenticated request has no tenant context")
    return tenant_id
from werkzeug.security import generate_password_hash, check_password_hash
from utils.validators import limpar_cpf
from utils.audit import registrar_auditoria_cursor

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

def criar_usuario(nome, usuario, senha, nivel, actor_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            login = (usuario or "").strip()
            cur.execute("SELECT 1 FROM platform_admins WHERE usuario = %s", (login,))
            if cur.fetchone():
                return "existe"
            cur.execute("SELECT 1 FROM usuarios WHERE usuario = %s", (login,))
            if cur.fetchone():
                return "existe"
            cur.execute("""
                INSERT INTO usuarios (condominio_id, nome, usuario, senha, nivel, ativo)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                tenant_id,
                (nome or "").strip().upper(),
                login,
                generate_password_hash(senha),
                (nivel or "funcionario").strip().lower(),
            ))
            novo = cur.fetchone()
            if actor_id:
                registrar_auditoria_cursor(cur, "usuario.criado", usuario_id=actor_id, condominio_id=tenant_id, entidade="usuario", entidade_id=novo["id"], detalhes={"nivel": nivel})
        conn.commit()
        logger.info("Usuário criado: %s", usuario)
        return novo
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def listar_usuarios():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, condominio_id, nome, usuario, nivel, ativo, criado_em FROM usuarios WHERE condominio_id = %s ORDER BY nome", (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_usuario_por_id(usuario_id, exigir_tenant=False):
    tenant_id = _tenant_id() if exigir_tenant else None
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if exigir_tenant:
                cur.execute(
                    """SELECT u.id, u.condominio_id, u.nome, u.usuario, u.nivel, u.ativo, u.criado_em,
                              c.ativo AS condominio_ativo
                       FROM usuarios u
                       JOIN condominios c ON c.id = u.condominio_id
                       WHERE u.id = %s AND u.condominio_id = %s""",
                    (usuario_id, tenant_id)
                )
            else:
                cur.execute(
                    """SELECT u.id, u.condominio_id, u.nome, u.usuario, u.nivel, u.ativo, u.criado_em,
                              c.ativo AS condominio_ativo
                       FROM usuarios u
                       JOIN condominios c ON c.id = u.condominio_id
                       WHERE u.id = %s""",
                    (usuario_id,)
                )
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_usuario(usuario, condominio_slug=None):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if condominio_slug:
                cur.execute("""SELECT u.id, u.condominio_id, u.nome, u.usuario, u.senha, u.nivel, u.ativo
                               FROM usuarios u JOIN condominios c ON c.id=u.condominio_id
                               WHERE u.usuario=%s AND c.slug=%s AND c.ativo=TRUE""", ((usuario or "").strip(), condominio_slug.strip().lower()))
            else:
                cur.execute("""SELECT id, condominio_id, nome, usuario, senha, nivel, ativo
                               FROM usuarios WHERE usuario=%s ORDER BY id LIMIT 2""", ((usuario or "").strip(),))
                rows=cur.fetchall()
                return rows[0] if len(rows)==1 else None
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_platform_admin(usuario):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, nome, usuario, senha, ativo
                           FROM platform_admins
                           WHERE usuario=%s AND ativo=TRUE""", ((usuario or "").strip(),))
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_platform_admin_por_id(admin_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, nome, usuario, ativo
                           FROM platform_admins
                           WHERE id=%s AND ativo=TRUE""", (admin_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


def verificar_senha(usuario_banco, senha_digitada):
    if not usuario_banco or not usuario_banco.get("ativo"):
        return False
    return check_password_hash(usuario_banco.get("senha", ""), senha_digitada)


def atualizar_usuario(usuario_id, nome, usuario, nivel, actor_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            login = (usuario or "").strip()
            cur.execute("SELECT 1 FROM platform_admins WHERE usuario = %s", (login,))
            if cur.fetchone():
                return "existe"
            cur.execute("SELECT 1 FROM usuarios WHERE usuario = %s AND id <> %s", (login, usuario_id))
            if cur.fetchone():
                return "existe"
            cur.execute("""
                UPDATE usuarios SET nome = %s, usuario = %s, nivel = %s WHERE id = %s AND condominio_id = %s
            """, (
                (nome or "").strip().upper(),
                login,
                (nivel or "funcionario").strip().lower(),
                usuario_id,
                tenant_id,
            ))
            alterou = cur.rowcount > 0
            if alterou and actor_id:
                registrar_auditoria_cursor(cur, "usuario.atualizado", usuario_id=actor_id, condominio_id=tenant_id, entidade="usuario", entidade_id=usuario_id, detalhes={"nivel": nivel})
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_senha_usuario(usuario_id, nova_senha, actor_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET senha = %s WHERE id = %s AND condominio_id = %s",
                (generate_password_hash(nova_senha), usuario_id, tenant_id)
            )
            alterou = cur.rowcount > 0
            if alterou and actor_id:
                registrar_auditoria_cursor(cur, "usuario.senha_alterada", usuario_id=actor_id, condominio_id=tenant_id, entidade="usuario", entidade_id=usuario_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def inativar_usuario(usuario_id, actor_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT nivel,ativo FROM usuarios WHERE id=%s AND condominio_id=%s FOR UPDATE", (usuario_id, tenant_id))
            alvo = cur.fetchone()
            if not alvo or not alvo["ativo"]:
                return False
            if alvo["nivel"] == "admin":
                cur.execute("SELECT COUNT(*) AS total FROM usuarios WHERE condominio_id=%s AND nivel='admin' AND ativo=TRUE", (tenant_id,))
                if cur.fetchone()["total"] <= 1:
                    raise ValueError("O condomínio precisa manter pelo menos um administrador ativo.")
            cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s AND condominio_id = %s", (usuario_id, tenant_id))
            if actor_id:
                registrar_auditoria_cursor(cur, "usuario.inativado", usuario_id=actor_id, condominio_id=tenant_id, entidade="usuario", entidade_id=usuario_id)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def ativar_usuario(usuario_id, actor_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo = TRUE WHERE id = %s AND condominio_id = %s AND ativo=FALSE", (usuario_id, tenant_id))
            alterou = cur.rowcount > 0
            if alterou and actor_id:
                registrar_auditoria_cursor(cur, "usuario.ativado", usuario_id=actor_id, condominio_id=tenant_id, entidade="usuario", entidade_id=usuario_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# UNIDADES
# ──────────────────────────────────────────────────────────────

def listar_unidades():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descricao, ativo FROM unidades WHERE condominio_id = %s AND ativo = TRUE ORDER BY codigo", (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def criar_unidade(codigo, descricao=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO unidades (condominio_id, codigo, descricao)
                VALUES (%s, %s, %s)
                ON CONFLICT (condominio_id, codigo) DO NOTHING
                RETURNING id
            """, (tenant_id, (codigo or "").strip().upper(), (descricao or "").strip()))
            resultado = cur.fetchone()
        conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_unidade_por_id(unidade_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descricao, ativo FROM unidades WHERE id = %s AND condominio_id = %s", (unidade_id, tenant_id))
            return cur.fetchone()
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# MORADORES
# ──────────────────────────────────────────────────────────────

def cadastrar_morador(nome, cpf, telefone, email, unidade_id, observacao):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if unidade_id:
                cur.execute("SELECT 1 FROM unidades WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (unidade_id, tenant_id))
                if not cur.fetchone():
                    raise ValueError("Unidade inválida para este condomínio.")
            cur.execute("""
                INSERT INTO moradores (condominio_id, nome, cpf, telefone, email, unidade_id, observacao, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                tenant_id,
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



def cadastrar_morador_com_unidade(nome, cpf, telefone, email, unidade_id, nova_unidade, observacao, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            resolved_unidade_id = unidade_id or None
            if resolved_unidade_id:
                cur.execute("SELECT 1 FROM unidades WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (resolved_unidade_id, tenant_id))
                if not cur.fetchone():
                    raise ValueError("Unidade inválida para este condomínio.")
            elif nova_unidade:
                codigo = nova_unidade.strip().upper()
                cur.execute("SELECT id, ativo FROM unidades WHERE condominio_id=%s AND codigo=%s FOR UPDATE", (tenant_id, codigo))
                existente = cur.fetchone()
                if existente:
                    if not existente["ativo"]:
                        raise ValueError("Esta unidade existe, mas está inativa. Reative a unidade antes de vinculá-la.")
                    resolved_unidade_id = existente["id"]
                else:
                    cur.execute("""
                        INSERT INTO unidades (condominio_id, codigo, descricao, ativo)
                        VALUES (%s, %s, NULL, TRUE)
                        RETURNING id
                    """, (tenant_id, codigo))
                    resolved_unidade_id = cur.fetchone()["id"]
            cur.execute("""
                INSERT INTO moradores (condominio_id, nome, cpf, telefone, email, unidade_id, observacao, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (tenant_id, (nome or "").strip().upper(), limpar_cpf(cpf) or None,
                  (telefone or "").strip() or None, (email or "").strip().lower() or None,
                  resolved_unidade_id, (observacao or "").strip().upper() or None))
            novo = cur.fetchone()
            if usuario_id:
                registrar_auditoria_cursor(cur, "morador.criado", usuario_id=usuario_id, condominio_id=tenant_id, entidade="morador", entidade_id=novo["id"])
        conn.commit()
        return novo["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)

def listar_moradores(apenas_ativos=True):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            filtro = "AND m.ativo = TRUE" if apenas_ativos else ""
            cur.execute(f"""
                SELECT
                    m.id, m.nome, m.cpf, m.telefone, m.email,
                    m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                    m.ativo, m.observacao, m.criado_em
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                WHERE m.condominio_id = %s {filtro}
                ORDER BY m.nome
            """, (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_moradores(termo):
    tenant_id = _tenant_id()
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
                    LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                    WHERE m.condominio_id = %s AND m.ativo = TRUE
                    ORDER BY m.nome
                    LIMIT 30
                """, (tenant_id,))
            else:
                like = f"%{termo}%"
                cur.execute("""
                    SELECT m.id, m.nome, m.cpf, m.telefone, m.email,
                           m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                           m.ativo, m.observacao, m.criado_em
                    FROM moradores m
                    LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                    WHERE m.condominio_id = %s AND m.ativo = TRUE
                      AND (m.nome ILIKE %s OR m.cpf ILIKE %s OR u.codigo ILIKE %s)
                    ORDER BY m.nome
                    LIMIT 30
                """, (tenant_id, like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_morador_por_id(morador_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.nome, m.cpf, m.telefone, m.email,
                       m.unidade_id, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao,
                       m.ativo, m.observacao, m.criado_em
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                WHERE m.id = %s AND m.condominio_id = %s
            """, (morador_id, tenant_id))
            return cur.fetchone()
    finally:
        liberar(conn)


def atualizar_morador(morador_id, nome, cpf, telefone, email, unidade_id, observacao, nova_unidade=None, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            resolved_unidade_id = unidade_id or None
            if resolved_unidade_id:
                cur.execute("SELECT 1 FROM unidades WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (resolved_unidade_id, tenant_id))
                if not cur.fetchone():
                    raise ValueError("Unidade inválida para este condomínio.")
            elif nova_unidade:
                codigo = nova_unidade.strip().upper()
                cur.execute("SELECT id, ativo FROM unidades WHERE condominio_id=%s AND codigo=%s FOR UPDATE", (tenant_id, codigo))
                existente = cur.fetchone()
                if existente:
                    if not existente["ativo"]:
                        raise ValueError("Esta unidade existe, mas está inativa. Reative a unidade antes de vinculá-la.")
                    resolved_unidade_id = existente["id"]
                else:
                    cur.execute("""
                        INSERT INTO unidades (condominio_id, codigo, descricao, ativo)
                        VALUES (%s, %s, NULL, TRUE)
                        RETURNING id
                    """, (tenant_id, codigo))
                    resolved_unidade_id = cur.fetchone()["id"]
            cur.execute("""
                UPDATE moradores
                SET nome = %s, cpf = %s, telefone = %s, email = %s,
                    unidade_id = %s, observacao = %s
                WHERE id = %s AND condominio_id = %s
            """, (
                (nome or "").strip().upper(),
                limpar_cpf(cpf) or None,
                (telefone or "").strip() or None,
                (email or "").strip().lower() or None,
                resolved_unidade_id,
                (observacao or "").strip().upper() or None,
                morador_id,
                tenant_id,
            ))
            if cur.rowcount == 0:
                raise ValueError("Morador não encontrado neste condomínio.")
            if usuario_id:
                registrar_auditoria_cursor(cur, "morador.atualizado", usuario_id=usuario_id, condominio_id=tenant_id, entidade="morador", entidade_id=morador_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def inativar_morador(morador_id, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE moradores SET ativo = FALSE WHERE id = %s AND condominio_id = %s AND ativo=TRUE", (morador_id, tenant_id))
            alterou = cur.rowcount > 0
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "morador.inativado", usuario_id=usuario_id, condominio_id=tenant_id, entidade="morador", entidade_id=morador_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def ativar_morador(morador_id, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE moradores SET ativo = TRUE WHERE id = %s AND condominio_id = %s AND ativo=FALSE", (morador_id, tenant_id))
            alterou = cur.rowcount > 0
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "morador.ativado", usuario_id=usuario_id, condominio_id=tenant_id, entidade="morador", entidade_id=morador_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def cpf_morador_ja_cadastrado(cpf, morador_id=None):
    tenant_id = _tenant_id()
    cpf = limpar_cpf(cpf)
    if not cpf:
        return None
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if morador_id:
                cur.execute(
                    "SELECT id, nome FROM moradores WHERE condominio_id = %s AND cpf = %s AND id <> %s LIMIT 1",
                    (tenant_id, cpf, morador_id)
                )
            else:
                cur.execute("SELECT id, nome FROM moradores WHERE condominio_id = %s AND cpf = %s LIMIT 1", (tenant_id, cpf))
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_moradores_ajax(termo):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            like = f"%{(termo or '').strip()}%"
            cur.execute("""
                SELECT m.id, m.nome, u.codigo AS unidade_codigo, u.descricao AS unidade_descricao
                FROM moradores m
                LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                WHERE m.condominio_id = %s AND m.ativo = TRUE
                  AND (m.nome ILIKE %s OR u.codigo ILIKE %s)
                ORDER BY m.nome
                LIMIT 15
            """, (tenant_id, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def total_moradores():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM moradores WHERE condominio_id = %s AND ativo = TRUE", (tenant_id,))
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


# ──────────────────────────────────────────────────────────────
# VISITANTES
# ──────────────────────────────────────────────────────────────

def cpf_ja_cadastrado(cpf, visitante_id=None):
    tenant_id = _tenant_id()
    cpf = limpar_cpf(cpf)
    if not cpf:
        return None
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if visitante_id:
                cur.execute(
                    "SELECT id, nome FROM visitantes WHERE condominio_id = %s AND cpf = %s AND id <> %s LIMIT 1",
                    (tenant_id, cpf, visitante_id)
                )
            else:
                cur.execute("SELECT id, nome FROM visitantes WHERE condominio_id = %s AND cpf = %s LIMIT 1", (tenant_id, cpf))
            return cur.fetchone()
    finally:
        liberar(conn)


def cadastrar_visitante(nome, cpf, tipo, placa, modelo, marca, foto, observacao,
                       entrada=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO visitantes (condominio_id, nome, cpf, tipo, placa, modelo, marca, foto, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id,
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
            if entrada:
                unidade_id = entrada.get("unidade_id") or None
                morador_id = entrada.get("morador_id") or None
                if unidade_id:
                    cur.execute("SELECT 1 FROM unidades WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (unidade_id, tenant_id))
                    if not cur.fetchone():
                        raise ValueError("Unidade inválida para este condomínio.")
                if morador_id:
                    cur.execute("SELECT unidade_id FROM moradores WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (morador_id, tenant_id))
                    morador = cur.fetchone()
                    if not morador:
                        raise ValueError("Morador inválido para este condomínio.")
                    if unidade_id and morador["unidade_id"] != unidade_id:
                        raise ValueError("O morador selecionado não pertence à unidade informada.")
                    unidade_id = unidade_id or morador["unidade_id"]
                cur.execute("SELECT 1 FROM usuarios WHERE id=%s AND condominio_id=%s AND ativo=TRUE", (entrada.get("usuario_id"), tenant_id))
                if not cur.fetchone():
                    raise ValueError("Usuário de entrada inválido para este condomínio.")
                cur.execute("""
                    INSERT INTO visitas
                        (condominio_id, visitante_id, endereco, placa, marca, modelo, observacao,
                         usuario_entrada_id, unidade_id, morador_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    tenant_id, novo["id"], (entrada.get("endereco") or "").strip().upper(),
                    (placa or "").strip().upper(), (marca or "").strip().upper(),
                    (modelo or "").strip().upper(), (observacao or "").strip().upper(),
                    entrada.get("usuario_id"), unidade_id, morador_id,
                ))
        conn.commit()
        return novo["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_visitantes(termo):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            termo = (termo or "").strip()
            if not termo:
                cur.execute("""
                    SELECT v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                           (SELECT vi.endereco FROM visitas vi
                            WHERE vi.condominio_id = %s AND vi.visitante_id = v.id
                            ORDER BY vi.data_entrada DESC LIMIT 1) AS ultimo_endereco
                    FROM visitantes v
                    WHERE v.condominio_id = %s
                    ORDER BY v.id DESC LIMIT 20
                """, (tenant_id, tenant_id))
            else:
                like = f"%{termo}%"
                cur.execute("""
                    SELECT v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                           (SELECT vi.endereco FROM visitas vi
                            WHERE vi.condominio_id = %s AND vi.visitante_id = v.id
                            ORDER BY vi.data_entrada DESC LIMIT 1) AS ultimo_endereco
                    FROM visitantes v
                    WHERE v.condominio_id = %s
                      AND (v.nome ILIKE %s OR v.cpf ILIKE %s OR v.placa ILIKE %s)
                    ORDER BY v.id DESC LIMIT 20
                """, (tenant_id, tenant_id, like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_um_por_cpf(cpf):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes WHERE condominio_id = %s AND cpf = %s LIMIT 1
            """, (tenant_id, limpar_cpf(cpf)))
            return cur.fetchone()
    finally:
        liberar(conn)


def buscar_visitante_por_id(visitante_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes WHERE condominio_id = %s AND id = %s
            """, (tenant_id, visitante_id))
            return cur.fetchone()
    finally:
        liberar(conn)


def listar_visitantes_paginado(pagina=1, por_pagina=20):
    tenant_id = _tenant_id()
    conn = conectar()
    offset = (pagina - 1) * por_pagina
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, cpf, tipo, placa, modelo, marca, foto, observacao
                FROM visitantes WHERE condominio_id = %s ORDER BY id DESC LIMIT %s OFFSET %s
            """, (tenant_id, por_pagina, offset))
            visitantes = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM visitantes WHERE condominio_id = %s", (tenant_id,))
            total = cur.fetchone()["total"]
        return visitantes, total
    finally:
        liberar(conn)


def atualizar_visitante(visitante_id, nome, cpf, tipo, placa, modelo, marca, foto, observacao):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if foto:
                cur.execute("""
                    UPDATE visitantes
                    SET nome=%s, cpf=%s, tipo=%s, placa=%s, modelo=%s, marca=%s, foto=%s, observacao=%s
                    WHERE id=%s AND condominio_id=%s
                """, (
                    (nome or "").strip().upper(), limpar_cpf(cpf),
                    (tipo or "").strip().upper(), (placa or "").strip().upper(),
                    (modelo or "").strip().upper(), (marca or "").strip().upper(),
                    foto, (observacao or "").strip().upper(), visitante_id, tenant_id,
                ))
            else:
                cur.execute("""
                    UPDATE visitantes
                    SET nome=%s, cpf=%s, tipo=%s, placa=%s, modelo=%s, marca=%s, observacao=%s
                    WHERE id=%s AND condominio_id=%s
                """, (
                    (nome or "").strip().upper(), limpar_cpf(cpf),
                    (tipo or "").strip().upper(), (placa or "").strip().upper(),
                    (modelo or "").strip().upper(), (marca or "").strip().upper(),
                    (observacao or "").strip().upper(), visitante_id, tenant_id,
                ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def remover_visitante(visitante_id, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM visitas WHERE visitante_id=%s AND condominio_id=%s LIMIT 1", (visitante_id, tenant_id))
            if cur.fetchone():
                raise ValueError("Visitante com histórico de visitas não pode ser excluído. Mantenha o cadastro para preservar o histórico.")
            cur.execute("DELETE FROM visitantes WHERE id = %s AND condominio_id = %s", (visitante_id, tenant_id))
            alterou = cur.rowcount > 0
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "visitante.removido", usuario_id=usuario_id, condominio_id=tenant_id, entidade="visitante", entidade_id=visitante_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_foto_visitante(visitante_id, nome_arquivo):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE visitantes SET foto = %s WHERE id = %s AND condominio_id = %s", (nome_arquivo, visitante_id, tenant_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_observacao_visitante(visitante_id, observacao, usuario_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visitantes SET observacao = %s WHERE id = %s AND condominio_id = %s",
                ((observacao or "").strip().upper(), visitante_id, tenant_id)
            )
            alterou = cur.rowcount > 0
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "visitante.observacao_atualizada", usuario_id=usuario_id, condominio_id=tenant_id, entidade="visitante", entidade_id=visitante_id)
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def listar_cpfs_visitantes():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cpf FROM visitantes WHERE condominio_id = %s", (tenant_id,))
            return {row["cpf"] for row in cur.fetchall() if row["cpf"]}
    finally:
        liberar(conn)


def importar_visitantes_em_lotes(lista_visitantes, tamanho_lote=100):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO visitantes (condominio_id, nome, cpf, tipo, placa, modelo, marca, foto, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (condominio_id, cpf) WHERE condominio_id IS NOT NULL DO NOTHING
            """
            for i in range(0, len(lista_visitantes), tamanho_lote):
                lote = [(tenant_id, *row) for row in lista_visitantes[i:i + tamanho_lote]]
                cur.executemany(query, lote)
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
                      observacao=None, usuario_id=None, unidade_id=None, morador_id=None, auditar=True):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            # Atualiza dados do veículo no cadastro do visitante
            cur.execute("""
                UPDATE visitantes
                SET placa = COALESCE(NULLIF(%s,''), placa),
                    marca  = COALESCE(NULLIF(%s,''), marca),
                    modelo = COALESCE(NULLIF(%s,''), modelo)
                WHERE id = %s AND condominio_id = %s
            """, (
                (placa or "").strip().upper(),
                (marca or "").strip().upper(),
                (modelo or "").strip().upper(),
                visitante_id,
                tenant_id,
            ))

            if unidade_id:
                cur.execute("SELECT 1 FROM unidades WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (unidade_id, tenant_id))
                if not cur.fetchone():
                    raise ValueError("Unidade inválida para este condomínio.")
            if morador_id:
                cur.execute("SELECT unidade_id FROM moradores WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (morador_id, tenant_id))
                morador = cur.fetchone()
                if not morador:
                    raise ValueError("Morador inválido para este condomínio.")
                if unidade_id and morador["unidade_id"] != unidade_id:
                    raise ValueError("O morador selecionado não pertence à unidade informada.")
                unidade_id = unidade_id or morador["unidade_id"]
            cur.execute("SELECT 1 FROM usuarios WHERE id=%s AND condominio_id=%s AND ativo=TRUE", (usuario_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Usuário de entrada inválido para este condomínio.")
            cur.execute("SELECT 1 FROM visitantes WHERE id = %s AND condominio_id = %s", (visitante_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Visitante inválido para este condomínio.")
            cur.execute("SELECT 1 FROM visitas WHERE condominio_id = %s AND visitante_id = %s AND data_saida IS NULL", (tenant_id, visitante_id))
            if cur.fetchone():
                raise ValueError("Este visitante já possui uma entrada ativa.")

            cur.execute("""
                INSERT INTO visitas
                    (condominio_id, visitante_id, endereco, placa, marca, modelo, observacao,
                     usuario_entrada_id, unidade_id, morador_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id,
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
            if auditar:
                registrar_auditoria_cursor(cur, "visita.entrada", usuario_id=usuario_id, condominio_id=tenant_id, entidade="visitante", entidade_id=visitante_id, detalhes={"visita_id": nova_visita["id"]})
        conn.commit()
        logger.info("Entrada registrada: visitante=%s visita=%s", visitante_id, nova_visita["id"])
        return nova_visita["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def registrar_saida(visitante_id, usuario_saida_id=None):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM usuarios WHERE id=%s AND condominio_id=%s AND ativo=TRUE", (usuario_saida_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Usuário de saída inválido para este condomínio.")
            cur.execute("""
                UPDATE visitas
                SET data_saida = CURRENT_TIMESTAMP, usuario_saida_id = %s
                WHERE condominio_id = %s AND id = (
                    SELECT id FROM visitas
                    WHERE condominio_id = %s AND visitante_id = %s AND data_saida IS NULL
                    ORDER BY data_entrada DESC LIMIT 1
                )
            """, (usuario_saida_id, tenant_id, tenant_id, visitante_id))
            alterou = cur.rowcount > 0
            if alterou:
                registrar_auditoria_cursor(cur, "visita.saida", usuario_id=usuario_saida_id, condominio_id=tenant_id, entidade="visitante", entidade_id=visitante_id)
        conn.commit()
        if alterou:
            logger.info("Saída registrada: visitante=%s", visitante_id)
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def visitantes_ativos():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    v.id, v.nome, v.cpf, v.tipo, v.placa, v.modelo, v.marca, v.foto, v.observacao,
                    vi.id AS visita_id, vi.endereco, vi.data_entrada,
                    m.nome AS morador_nome, u.codigo AS unidade_codigo
                FROM visitantes v
                INNER JOIN visitas vi ON v.id = vi.visitante_id AND v.condominio_id = vi.condominio_id AND vi.data_saida IS NULL AND vi.condominio_id = %s
                LEFT JOIN moradores m ON m.id = vi.morador_id AND m.condominio_id = vi.condominio_id
                LEFT JOIN unidades u ON u.id = vi.unidade_id AND u.condominio_id = vi.condominio_id
                ORDER BY vi.data_entrada DESC
            """, (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def buscar_ativos(termo):
    tenant_id = _tenant_id()
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
                INNER JOIN visitas vi ON v.id = vi.visitante_id AND v.condominio_id = vi.condominio_id AND vi.data_saida IS NULL
                LEFT JOIN moradores m ON m.id = vi.morador_id AND m.condominio_id = vi.condominio_id
                LEFT JOIN unidades u ON u.id = vi.unidade_id AND u.condominio_id = vi.condominio_id
                WHERE vi.condominio_id = %s AND (v.nome ILIKE %s OR v.cpf ILIKE %s OR v.placa ILIKE %s OR vi.endereco ILIKE %s)
                ORDER BY vi.data_entrada DESC
            """, (tenant_id, like, like, like, like))
            return cur.fetchall()
    finally:
        liberar(conn)


def historico_visitante(visitante_id):
    tenant_id = _tenant_id()
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
                LEFT JOIN usuarios ue ON vi.usuario_entrada_id = ue.id AND ue.condominio_id = vi.condominio_id
                LEFT JOIN usuarios us ON vi.usuario_saida_id = us.id AND us.condominio_id = vi.condominio_id
                LEFT JOIN moradores m ON vi.morador_id = m.id AND m.condominio_id = vi.condominio_id
                LEFT JOIN unidades u ON vi.unidade_id = u.id AND u.condominio_id = vi.condominio_id
                WHERE vi.condominio_id = %s AND vi.visitante_id = %s
                ORDER BY vi.data_entrada DESC
            """, (tenant_id, visitante_id))
            return cur.fetchall()
    finally:
        liberar(conn)


def atualizar_visita_ativa(visitante_id, endereco):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE visitas SET endereco = %s
                WHERE id = (
                    SELECT id FROM visitas
                    WHERE condominio_id = %s AND visitante_id = %s AND data_saida IS NULL
                    ORDER BY data_entrada DESC LIMIT 1
                ) AND condominio_id = %s
            """, ((endereco or "").strip().upper(), tenant_id, visitante_id, tenant_id))
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
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitantes WHERE condominio_id = %s", (tenant_id,))
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_visitantes_ativos():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE condominio_id = %s AND data_saida IS NULL", (tenant_id,))
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_entradas_hoje():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE condominio_id = %s AND DATE(data_entrada) = CURRENT_DATE", (tenant_id,))
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def total_saidas_hoje():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM visitas WHERE condominio_id = %s AND DATE(data_saida) = CURRENT_DATE", (tenant_id,))
            r = cur.fetchone()
            return r["total"] if r else 0
    finally:
        liberar(conn)


def ultima_entrada():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.nome, vi.data_entrada
                FROM visitas vi
                JOIN visitantes v ON v.id = vi.visitante_id AND v.condominio_id = vi.condominio_id
                WHERE vi.condominio_id = %s
                ORDER BY vi.data_entrada DESC LIMIT 1
            """, (tenant_id,))
            r = cur.fetchone()
            if not r:
                return ("-", "-")
            return r["nome"], r["data_entrada"].strftime("%H:%M") if r["data_entrada"] else "-"
    finally:
        liberar(conn)


def ultimas_entradas_dashboard(limite=5):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.nome, v.foto, vi.endereco, vi.data_entrada,
                       m.nome AS morador_nome, u.codigo AS unidade_codigo
                FROM visitas vi
                JOIN visitantes v ON v.id = vi.visitante_id AND v.condominio_id = vi.condominio_id
                LEFT JOIN moradores m ON vi.morador_id = m.id AND m.condominio_id = vi.condominio_id
                LEFT JOIN unidades u ON vi.unidade_id = u.id AND u.condominio_id = vi.condominio_id
                WHERE vi.condominio_id = %s
                ORDER BY vi.data_entrada DESC LIMIT %s
            """, (tenant_id, limite))
            return cur.fetchall()
    finally:
        liberar(conn)
