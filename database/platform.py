from database.connection import conectar, liberar


def listar_condominios_com_metricas():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id,c.nome,c.slug,c.ativo,c.criado_em,
                       COUNT(u.id) AS total_usuarios,
                       COUNT(u.id) FILTER (WHERE u.ativo = TRUE) AS usuarios_ativos,
                       COUNT(u.id) FILTER (WHERE u.nivel = 'admin' AND u.ativo = TRUE) AS admins_ativos
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
                       COUNT(u.id) FILTER (WHERE u.ativo=TRUE) AS usuarios_ativos
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


def atualizar_condominio(condominio_id,nome,slug):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE condominios SET nome=%s,slug=%s WHERE id=%s RETURNING id",(nome,slug,condominio_id))
            row=cur.fetchone()
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)


def definir_status_condominio(condominio_id,ativo):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            if not ativo:
                cur.execute("SELECT COUNT(*) AS abertas FROM visitas WHERE condominio_id=%s AND data_saida IS NULL",(condominio_id,))
                if cur.fetchone()["abertas"] > 0:
                    raise ValueError("Existem visitas com entrada aberta. Registre as saídas antes de inativar o condomínio.")
            cur.execute("UPDATE condominios SET ativo=%s WHERE id=%s AND ativo IS DISTINCT FROM %s RETURNING id",(ativo,condominio_id,ativo))
            row=cur.fetchone()
        conn.commit(); return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)


def definir_status_usuario_tenant(condominio_id,usuario_id,ativo):
    conn=conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE usuarios SET ativo=%s WHERE id=%s AND condominio_id=%s
                           AND ativo IS DISTINCT FROM %s RETURNING id""",(ativo,usuario_id,condominio_id,ativo))
            row=cur.fetchone()
        conn.commit(); return bool(row)
    except Exception:
        conn.rollback(); raise
    finally:
        liberar(conn)
