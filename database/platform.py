from database.connection import conectar, liberar
from utils.audit import registrar_auditoria_cursor


def listar_condominios_com_metricas():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id,c.nome,c.slug,c.ativo,c.criado_em,
                       COUNT(u.id) AS total_usuarios,
                       COUNT(u.id) FILTER (WHERE u.ativo = TRUE) AS usuarios_ativos,
                       COUNT(u.id) FILTER (WHERE u.nivel = 'admin_condominio' AND u.ativo = TRUE) AS admins_ativos,
                       (SELECT COUNT(*) FROM visitas v WHERE v.condominio_id=c.id AND v.data_saida IS NULL) AS acessos_abertos,
                       (SELECT COUNT(*) FROM encomendas e WHERE e.condominio_id=c.id AND e.status NOT IN ('retirada','entregue_na_porta','cancelada')) AS encomendas_pendentes,
                       GREATEST(
                         COALESCE(MAX(u.criado_em), c.criado_em),
                         COALESCE((SELECT MAX(v.data_entrada) FROM visitas v WHERE v.condominio_id=c.id), c.criado_em),
                         COALESCE((SELECT MAX(e.atualizado_em) FROM encomendas e WHERE e.condominio_id=c.id), c.criado_em)
                       ) AS ultima_atividade
                FROM condominios c
                LEFT JOIN usuarios u ON u.condominio_id = c.id
                GROUP BY c.id,c.nome,c.slug,c.ativo,c.criado_em
                ORDER BY c.nome
            """)
            dados = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE ativo=TRUE) AS ativos FROM condominios")
            resumo = cur.fetchone()
        return dados, resumo
    finally:
        liberar(conn)


def buscar_condominio_detalhe(condominio_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id,c.nome,c.slug,c.ativo,c.criado_em,
                       COUNT(u.id) AS total_usuarios,
                       COUNT(u.id) FILTER (WHERE u.ativo=TRUE) AS usuarios_ativos,
                       COUNT(u.id) FILTER (WHERE u.nivel='admin_condominio' AND u.ativo=TRUE) AS admins_ativos,
                       (SELECT COUNT(*) FROM visitas v WHERE v.condominio_id=c.id AND v.data_saida IS NULL) AS acessos_abertos,
                       (SELECT COUNT(*) FROM encomendas e WHERE e.condominio_id=c.id AND e.status NOT IN ('retirada','entregue_na_porta','cancelada')) AS encomendas_pendentes,
                       (SELECT COUNT(*) FROM moradores m WHERE m.condominio_id=c.id AND m.ativo=TRUE) AS moradores_ativos,
                       (SELECT COUNT(*) FROM visitantes v WHERE v.condominio_id=c.id) AS visitantes_cadastrados,
                       GREATEST(
                         COALESCE(MAX(u.criado_em), c.criado_em),
                         COALESCE((SELECT MAX(v.data_entrada) FROM visitas v WHERE v.condominio_id=c.id), c.criado_em),
                         COALESCE((SELECT MAX(e.atualizado_em) FROM encomendas e WHERE e.condominio_id=c.id), c.criado_em)
                       ) AS ultima_atividade
                FROM condominios c LEFT JOIN usuarios u ON u.condominio_id=c.id
                WHERE c.id=%s GROUP BY c.id,c.nome,c.slug,c.ativo,c.criado_em
            """,(condominio_id,))
            condominio=cur.fetchone()
            if not condominio:
                return None, []
            cur.execute("""SELECT id,nome,usuario,nivel,ativo,criado_em FROM usuarios
                           WHERE condominio_id=%s ORDER BY ativo DESC,nome""",(condominio_id,))
            usuarios=cur.fetchall()
        return condominio, usuarios
    finally:
        liberar(conn)


def atualizar_condominio(condominio_id,nome,slug,actor_id=None):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            if actor_id:
                cur.execute("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE", (actor_id,))
                if not cur.fetchone():
                    raise ValueError("Administrador da plataforma inválido.")
            cur.execute("UPDATE condominios SET nome=%s,slug=%s WHERE id=%s RETURNING id",(nome,slug,condominio_id))
            row=cur.fetchone()
            if row and actor_id:
                registrar_auditoria_cursor(cur, "plataforma.condominio_atualizado", actor_tipo="platform_admin", actor_id=actor_id, entidade="condominio", entidade_id=condominio_id, detalhes={"slug": slug})
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)


def definir_status_condominio(condominio_id,ativo,actor_id=None):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            if actor_id:
                cur.execute("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE", (actor_id,))
                if not cur.fetchone():
                    raise ValueError("Administrador da plataforma inválido.")
            if not ativo:
                cur.execute("SELECT id FROM condominios WHERE id=%s FOR UPDATE", (condominio_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return False
                cur.execute("SELECT COUNT(*) AS abertas FROM visitas WHERE condominio_id=%s AND data_saida IS NULL",(condominio_id,))
                if cur.fetchone()["abertas"] > 0:
                    raise ValueError("Existem visitas com entrada aberta. Registre as saídas antes de inativar o condomínio.")
                cur.execute("""SELECT COUNT(*) AS pendentes FROM encomendas
                               WHERE condominio_id=%s AND status NOT IN ('retirada','entregue_na_porta','cancelada')""",(condominio_id,))
                if cur.fetchone()["pendentes"] > 0:
                    raise ValueError("Existem encomendas pendentes. Finalize ou cancele as encomendas antes de inativar o condomínio.")
            cur.execute("UPDATE condominios SET ativo=%s WHERE id=%s AND ativo IS DISTINCT FROM %s RETURNING id",(ativo,condominio_id,ativo))
            row=cur.fetchone()
            if row and actor_id:
                registrar_auditoria_cursor(cur, "plataforma.condominio_status", actor_tipo="platform_admin", actor_id=actor_id, entidade="condominio", entidade_id=condominio_id, detalhes={"ativo": ativo})
        conn.commit(); return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)


def definir_status_usuario_tenant(condominio_id,usuario_id,ativo,actor_id=None):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            # Use the same tenant lock as role changes and tenant-side deactivation.
            cur.execute("SELECT id FROM condominios WHERE id=%s FOR UPDATE", (condominio_id,))
            if not cur.fetchone():
                conn.rollback()
                return False
            if actor_id:
                cur.execute("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE", (actor_id,))
                if not cur.fetchone():
                    raise ValueError("Administrador da plataforma inválido.")
            cur.execute("SELECT id,nivel,ativo FROM usuarios WHERE id=%s AND condominio_id=%s FOR UPDATE",(usuario_id,condominio_id))
            alvo=cur.fetchone()
            if not alvo or alvo["ativo"] == ativo:
                conn.rollback()
                return False
            if not ativo and alvo["nivel"] == "admin_condominio":
                cur.execute("SELECT COUNT(*) AS total FROM usuarios WHERE condominio_id=%s AND nivel='admin_condominio' AND ativo=TRUE",(condominio_id,))
                if cur.fetchone()["total"] <= 1:
                    raise ValueError("O condomínio precisa manter pelo menos um administrador ativo.")
            cur.execute("UPDATE usuarios SET ativo=%s WHERE id=%s AND condominio_id=%s RETURNING id",(ativo,usuario_id,condominio_id))
            row=cur.fetchone()
            if row and actor_id:
                registrar_auditoria_cursor(cur, "plataforma.usuario_tenant_status", actor_tipo="platform_admin", actor_id=actor_id, condominio_id=condominio_id, entidade="usuario", entidade_id=usuario_id, detalhes={"ativo": ativo})
        conn.commit(); return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)


def criar_condominio_com_usuario(nome, slug, usuario_nome=None, usuario_login=None, usuario_senha_hash=None, nivel="admin_condominio", actor_id=None):
    if usuario_login and (nivel != "admin_condominio" or not usuario_nome or not usuario_senha_hash):
        raise ValueError("O acesso inicial do condomínio deve ser um administrador válido.")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if actor_id:
                cur.execute("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE", (actor_id,))
                if not cur.fetchone():
                    raise ValueError("Administrador da plataforma inválido.")
            cur.execute("INSERT INTO condominios(nome,slug,ativo) VALUES(%s,%s,TRUE) RETURNING id", (nome, slug))
            condominio_id = cur.fetchone()["id"]
            usuario_id = None
            if usuario_login:
                cur.execute("SELECT 1 FROM platform_admins WHERE usuario=%s", (usuario_login,))
                if cur.fetchone():
                    raise ValueError("Este login é reservado pela plataforma.")
                cur.execute("SELECT 1 FROM usuarios WHERE usuario=%s", (usuario_login,))
                if cur.fetchone():
                    raise ValueError("Este login já está em uso.")
                cur.execute("""INSERT INTO usuarios(condominio_id,nome,usuario,senha,nivel,ativo)
                               VALUES(%s,%s,%s,%s,%s,TRUE) RETURNING id""",
                            (condominio_id, usuario_nome.upper(), usuario_login, usuario_senha_hash, nivel))
                usuario_id = cur.fetchone()["id"]
            if actor_id:
                registrar_auditoria_cursor(cur, "plataforma.condominio_criado", actor_tipo="platform_admin", actor_id=actor_id, entidade="condominio", entidade_id=condominio_id, detalhes={"slug": slug})
                if usuario_id:
                    registrar_auditoria_cursor(cur, "plataforma.usuario_tenant_criado", actor_tipo="platform_admin", actor_id=actor_id, condominio_id=condominio_id, entidade="usuario", entidade_id=usuario_id, detalhes={"nivel": nivel})
        conn.commit()
        return condominio_id, usuario_id
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def criar_usuario_tenant(condominio_id, nome, usuario, senha_hash, nivel, actor_id=None):
    if nivel not in ("admin_condominio", "administrativo", "porteiro"):
        raise ValueError("Perfil de usuário inválido.")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if actor_id:
                cur.execute("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE", (actor_id,))
                if not cur.fetchone():
                    raise ValueError("Administrador da plataforma inválido.")
            cur.execute("SELECT id FROM condominios WHERE id=%s AND ativo=TRUE FOR UPDATE", (condominio_id,))
            if not cur.fetchone():
                raise ValueError("Condomínio não encontrado ou inativo.")
            cur.execute("SELECT COUNT(*) AS total FROM usuarios WHERE condominio_id=%s AND nivel='admin_condominio' AND ativo=TRUE", (condominio_id,))
            if cur.fetchone()["total"] == 0 and nivel != "admin_condominio":
                raise ValueError("Cadastre primeiro um administrador do condomínio.")
            cur.execute("SELECT 1 FROM platform_admins WHERE usuario=%s", (usuario,))
            if cur.fetchone():
                raise ValueError("Este login é reservado pela plataforma.")
            cur.execute("""INSERT INTO usuarios(condominio_id,nome,usuario,senha,nivel,ativo)
                           VALUES(%s,%s,%s,%s,%s,TRUE) RETURNING id""",
                        (condominio_id, nome.upper(), usuario, senha_hash, nivel))
            usuario_id = cur.fetchone()["id"]
            if actor_id:
                registrar_auditoria_cursor(cur, "plataforma.usuario_tenant_criado", actor_tipo="platform_admin", actor_id=actor_id, condominio_id=condominio_id, entidade="usuario", entidade_id=usuario_id, detalhes={"nivel": nivel})
        conn.commit()
        return usuario_id
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def resumo_operacional_plataforma():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  (SELECT COUNT(*) FROM condominios) AS tenants,
                  (SELECT COUNT(*) FROM condominios WHERE ativo=TRUE) AS tenants_ativos,
                  (SELECT COUNT(*) FROM usuarios WHERE ativo=TRUE) AS usuarios_ativos,
                  (SELECT COUNT(*) FROM visitas WHERE data_saida IS NULL) AS acessos_abertos,
                  (SELECT COUNT(*) FROM encomendas WHERE status NOT IN ('retirada','entregue_na_porta','cancelada')) AS encomendas_pendentes,
                  (SELECT COUNT(*) FROM audit_logs WHERE criado_em >= CURRENT_TIMESTAMP - INTERVAL '24 hours') AS eventos_24h
            """)
            resumo = cur.fetchone()
            cur.execute("""
                SELECT a.id,a.acao,a.entidade,a.entidade_id,a.criado_em,a.condominio_id,
                       c.nome AS condominio_nome
                FROM audit_logs a
                LEFT JOIN condominios c ON c.id=a.condominio_id
                WHERE a.actor_tipo='platform_admin'
                ORDER BY a.criado_em DESC
                LIMIT 12
            """)
            eventos = cur.fetchall()
        return resumo, eventos
    finally:
        liberar(conn)
