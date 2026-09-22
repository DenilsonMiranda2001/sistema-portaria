from database.connection import conectar, liberar
from database.models import _tenant_id
from utils.audit import registrar_auditoria_cursor


def _normalizar_documento(valor):
    return "".join(ch for ch in (valor or "").strip().upper() if ch.isalnum()) or None


def listar_entregadores(apenas_ativos=False):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if apenas_ativos:
                cur.execute("""
                    SELECT e.*,
                           COUNT(l.id)::int AS total_lotes,
                           MAX(l.data_chegada) AS ultima_entrega
                    FROM entregadores e
                    LEFT JOIN lotes_encomendas l
                      ON l.entregador_id=e.id AND l.condominio_id=e.condominio_id
                    WHERE e.condominio_id=%s AND e.ativo=TRUE
                    GROUP BY e.id
                    ORDER BY e.nome, e.id
                """, (tenant_id,))
            else:
                cur.execute("""
                    SELECT e.*,
                           COUNT(l.id)::int AS total_lotes,
                           MAX(l.data_chegada) AS ultima_entrega
                    FROM entregadores e
                    LEFT JOIN lotes_encomendas l
                      ON l.entregador_id=e.id AND l.condominio_id=e.condominio_id
                    WHERE e.condominio_id=%s
                    GROUP BY e.id
                    ORDER BY e.ativo DESC, e.nome, e.id
                """, (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)

def buscar_entregador(entregador_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       COUNT(l.id)::int AS total_lotes,
                       MAX(l.data_chegada) AS ultima_entrega
                FROM entregadores e
                LEFT JOIN lotes_encomendas l
                  ON l.entregador_id=e.id AND l.condominio_id=e.condominio_id
                WHERE e.id=%s AND e.condominio_id=%s
                GROUP BY e.id
            """, (entregador_id, tenant_id))
            return cur.fetchone()
    finally:
        liberar(conn)


def _validar_actor(cur, usuario_id, tenant_id):
    cur.execute(
        "SELECT 1 FROM usuarios WHERE id=%s AND condominio_id=%s AND ativo=TRUE",
        (usuario_id, tenant_id),
    )
    if not cur.fetchone():
        raise ValueError("Usuário inválido para este condomínio.")


def criar_entregador(nome, documento, telefone, transportadora, usuario_id):
    tenant_id = _tenant_id()
    nome = (nome or "").strip().upper()
    if not nome:
        raise ValueError("Informe o nome do entregador.")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            _validar_actor(cur, usuario_id, tenant_id)
            cur.execute("""
                INSERT INTO entregadores
                    (condominio_id, nome, documento, telefone, transportadora)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id, nome, _normalizar_documento(documento),
                (telefone or "").strip() or None,
                (transportadora or "").strip() or None,
            ))
            novo = cur.fetchone()
            registrar_auditoria_cursor(
                cur, "entregador.criado", usuario_id=usuario_id,
                condominio_id=tenant_id, entidade="entregador",
                entidade_id=novo["id"],
            )
        conn.commit()
        return novo["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def atualizar_entregador(entregador_id, nome, documento, telefone, transportadora, usuario_id):
    tenant_id = _tenant_id()
    nome = (nome or "").strip().upper()
    if not nome:
        raise ValueError("Informe o nome do entregador.")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            _validar_actor(cur, usuario_id, tenant_id)
            cur.execute("""
                UPDATE entregadores
                SET nome=%s, documento=%s, telefone=%s, transportadora=%s,
                    atualizado_em=CURRENT_TIMESTAMP
                WHERE id=%s AND condominio_id=%s
            """, (
                nome, _normalizar_documento(documento),
                (telefone or "").strip() or None,
                (transportadora or "").strip() or None,
                entregador_id, tenant_id,
            ))
            alterou = cur.rowcount > 0
            if alterou:
                registrar_auditoria_cursor(
                    cur, "entregador.atualizado", usuario_id=usuario_id,
                    condominio_id=tenant_id, entidade="entregador",
                    entidade_id=entregador_id,
                )
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def definir_status_entregador(entregador_id, ativo, usuario_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            _validar_actor(cur, usuario_id, tenant_id)
            cur.execute("""
                UPDATE entregadores
                SET ativo=%s, atualizado_em=CURRENT_TIMESTAMP
                WHERE id=%s AND condominio_id=%s AND ativo<>%s
            """, (ativo, entregador_id, tenant_id, ativo))
            alterou = cur.rowcount > 0
            if alterou:
                registrar_auditoria_cursor(
                    cur, "entregador.ativado" if ativo else "entregador.inativado",
                    usuario_id=usuario_id, condominio_id=tenant_id,
                    entidade="entregador", entidade_id=entregador_id,
                )
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
