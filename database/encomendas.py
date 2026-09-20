import secrets
import string
from datetime import datetime

from database.connection import conectar, liberar
from database.models import _tenant_id
from utils.audit import registrar_auditoria_cursor


STATUS_FINAIS = ("retirada", "entregue_na_porta", "cancelada")
STATUS_PENDENTES = ("retida_portaria",)


def _codigo_retirada(cur):
    tenant_id = _tenant_id()
    alfabeto = string.ascii_uppercase + string.digits
    ano = datetime.now().year
    for _ in range(20):
        codigo = f"ENC-{ano}-{''.join(secrets.choice(alfabeto) for _ in range(4))}"
        cur.execute("SELECT 1 FROM encomendas WHERE condominio_id = %s AND codigo_retirada = %s", (tenant_id, codigo))
        if not cur.fetchone():
            return codigo
    raise RuntimeError("Não foi possível gerar um código de retirada único.")


def criar_lote(nome_entregador, transportadora, observacao, usuario_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM usuarios WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (usuario_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Usuário inválido para este condomínio.")
            cur.execute("""
                INSERT INTO lotes_encomendas
                    (condominio_id, nome_entregador, transportadora, observacao, usuario_criacao_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id,
                (nome_entregador or "").strip().upper() or None,
                (transportadora or "").strip(),
                (observacao or "").strip() or None,
                usuario_id,
            ))
            lote = cur.fetchone()
            registrar_auditoria_cursor(cur, "encomenda.lote_criado", usuario_id=usuario_id, condominio_id=tenant_id, entidade="lote_encomenda", entidade_id=lote["id"])
        conn.commit()
        return lote["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_lote(lote_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.*, COUNT(e.id)::int AS total_encomendas
                FROM lotes_encomendas l
                LEFT JOIN encomendas e ON e.lote_id = l.id AND e.condominio_id = l.condominio_id
                WHERE l.id = %s AND l.condominio_id = %s
                GROUP BY l.id
            """, (lote_id, tenant_id))
            return cur.fetchone()
    finally:
        liberar(conn)


def listar_lotes():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.*,
                       COUNT(e.id)::int AS total,
                       COUNT(e.id) FILTER (WHERE e.status IN ('recebida','aguardando_resposta','morador_em_casa'))::int AS legadas,
                       COUNT(e.id) FILTER (WHERE e.status = 'retida_portaria')::int AS retidas,
                       COUNT(e.id) FILTER (WHERE e.status = 'retirada')::int AS retiradas
                FROM lotes_encomendas l
                LEFT JOIN encomendas e ON e.lote_id = l.id AND e.condominio_id = l.condominio_id
                WHERE l.condominio_id = %s
                GROUP BY l.id
                ORDER BY l.data_chegada DESC, l.id DESC
            """, (tenant_id,))
            return cur.fetchall()
    finally:
        liberar(conn)


def atualizar_status_lote(lote_id, status, usuario_id=None):
    tenant_id = _tenant_id()
    if status not in ("concluido", "cancelado"):
        return False
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE lotes_encomendas SET status = %s
                WHERE id = %s AND condominio_id = %s AND status IN ('aberto', 'em_triagem')
            """, (status, lote_id, tenant_id))
            alterou = cur.rowcount > 0
            if alterou and status == "cancelado":
                cur.execute("SELECT COUNT(*)::int AS total FROM encomendas WHERE lote_id=%s AND condominio_id=%s", (lote_id, tenant_id))
                if cur.fetchone()["total"] > 0:
                    raise ValueError("Recebimentos com encomendas registradas não podem ser cancelados em lote.")
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "encomenda.lote_status", usuario_id=usuario_id, condominio_id=tenant_id, entidade="lote_encomenda", entidade_id=lote_id, detalhes={"status": status})
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def adicionar_encomenda(lote_id, morador_id, unidade, nome_morador,
                        codigo_rastreio, descricao, observacao, usuario_id):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM usuarios WHERE id = %s AND condominio_id = %s AND ativo = TRUE", (usuario_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Usuário inválido para este condomínio.")
            telefone = None
            unidade_id = None
            if morador_id:
                cur.execute("""
                    SELECT m.id, m.nome, m.telefone, m.unidade_id, u.codigo AS unidade
                    FROM moradores m
                    LEFT JOIN unidades u ON u.id = m.unidade_id AND u.condominio_id = m.condominio_id
                    WHERE m.id = %s AND m.condominio_id = %s AND m.ativo = TRUE
                """, (morador_id, tenant_id))
                morador = cur.fetchone()
                if not morador:
                    raise ValueError("Morador selecionado não foi encontrado.")
                nome_morador = morador["nome"]
                unidade = morador["unidade"] or unidade
                unidade_id = morador["unidade_id"]
                telefone = morador["telefone"]

            cur.execute("SELECT 1 FROM lotes_encomendas WHERE id = %s AND condominio_id = %s AND status IN ('aberto','em_triagem')", (lote_id, tenant_id))
            if not cur.fetchone():
                raise ValueError("Lote não encontrado ou já encerrado.")

            unidade = (unidade or "").strip().upper()
            if not unidade:
                raise ValueError("Informe a unidade da encomenda.")

            codigo = _codigo_retirada(cur)
            cur.execute("""
                INSERT INTO encomendas (
                    condominio_id, lote_id, morador_id, unidade_id, nome_morador, unidade,
                    codigo_rastreio, descricao, status, codigo_retirada,
                    observacao, usuario_criacao_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'retida_portaria',
                        %s, %s, %s)
                RETURNING id, codigo_retirada
            """, (
                tenant_id, lote_id, morador_id or None, unidade_id,
                (nome_morador or "").strip().upper() or None, unidade,
                (codigo_rastreio or "").strip().upper() or None,
                (descricao or "").strip() or None, codigo,
                (observacao or "").strip() or None, usuario_id,
            ))
            nova = cur.fetchone()
            cur.execute("""
                UPDATE lotes_encomendas SET status = 'em_triagem'
                WHERE id = %s AND condominio_id = %s AND status = 'aberto'
            """, (lote_id, tenant_id))
            registrar_auditoria_cursor(cur, "encomenda.criada", usuario_id=usuario_id, condominio_id=tenant_id, entidade="encomenda", entidade_id=nova["id"], detalhes={"lote_id": lote_id})
        conn.commit()
        nova["telefone"] = telefone
        return nova
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def _select_encomendas(where="", order="e.data_chegada DESC, e.id DESC", params=()):
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT e.*, l.transportadora, l.nome_entregador, l.status AS lote_status,
                       m.telefone
                FROM encomendas e
                JOIN lotes_encomendas l ON l.id = e.lote_id AND l.condominio_id = e.condominio_id
                LEFT JOIN moradores m ON m.id = e.morador_id AND m.condominio_id = e.condominio_id
                WHERE e.condominio_id = %s {where}
                ORDER BY {order}
            """, (tenant_id, *params))
            return cur.fetchall()
    finally:
        liberar(conn)


def listar_encomendas_lote(lote_id):
    tenant_id = _tenant_id()
    return _select_encomendas("AND e.lote_id = %s", "e.id DESC", (lote_id,))


def buscar_encomenda(encomenda_id):
    tenant_id = _tenant_id()
    dados = _select_encomendas("AND e.id = %s", params=(encomenda_id,))
    return dados[0] if dados else None


def listar_encomendas(filtro=None, termo=None, lote_id=None, transportadora=None):
    tenant_id = _tenant_id()
    clausulas = []
    params = []
    if filtro == "hoje":
        clausulas.append("e.data_chegada::date = CURRENT_DATE")
    elif filtro == "pendentes":
        clausulas.append("e.status = 'retida_portaria'")
    elif filtro == "retidas":
        clausulas.append("e.status = 'retida_portaria'")
    elif filtro == "retiradas":
        clausulas.append("e.status = 'retirada'")
    elif filtro == "historico":
        clausulas.append("e.status IN ('retirada','entregue_na_porta','cancelada')")
    if termo:
        clausulas.append("""(
            UPPER(e.unidade) LIKE UPPER(%s) OR
            UPPER(COALESCE(e.nome_morador, '')) LIKE UPPER(%s) OR
            UPPER(e.codigo_retirada) LIKE UPPER(%s) OR
            UPPER(COALESCE(e.codigo_rastreio, '')) LIKE UPPER(%s)
        )""")
        busca = f"%{termo.strip()}%"
        params.extend([busca] * 4)
    if lote_id:
        clausulas.append("e.lote_id = %s")
        params.append(lote_id)
    if transportadora:
        clausulas.append("l.transportadora = %s")
        params.append(transportadora)
    where = f"AND {' AND '.join(clausulas)}" if clausulas else ""
    return _select_encomendas(where, params=tuple(params))


def resumo_painel():
    tenant_id = _tenant_id()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE data_chegada::date = CURRENT_DATE)::int AS recebidas_hoje,
                    COUNT(*) FILTER (WHERE status = 'retida_portaria')::int AS aguardando,
                    COUNT(*) FILTER (WHERE status = 'retida_portaria')::int AS retidas,
                    COUNT(*) FILTER (WHERE status = 'retirada'
                                      AND data_retirada::date = CURRENT_DATE)::int AS retiradas_hoje,
                    COUNT(*) FILTER (WHERE status IN ('retirada','cancelada')
                                      AND atualizado_em::date = CURRENT_DATE)::int AS finalizadas_hoje
                FROM encomendas
                WHERE condominio_id = %s
            """, (tenant_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


TRANSICOES_ENCOMENDA = {
    # Legacy states can only move forward into the centralized custody workflow.
    "recebida": {"retida_portaria", "cancelada"},
    "aguardando_resposta": {"retida_portaria", "cancelada"},
    "morador_em_casa": {"retida_portaria", "cancelada"},
    "retida_portaria": {"retirada", "cancelada"},
    "retirada": set(),
    "entregue_na_porta": set(),
    "cancelada": set(),
}


def atualizar_status_encomenda(encomenda_id, status, retirado_por=None, usuario_id=None):
    tenant_id = _tenant_id()
    if status not in TRANSICOES_ENCOMENDA:
        raise ValueError("Status inválido.")
    retirado_por = (retirado_por or "").strip().upper()
    if status == "retirada" and not retirado_por:
        raise ValueError("Informe quem retirou a encomenda.")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM encomendas WHERE id=%s AND condominio_id=%s FOR UPDATE", (encomenda_id, tenant_id))
            atual = cur.fetchone()
            if not atual:
                raise ValueError("Encomenda não encontrada.")
            status_atual = atual["status"]
            if status == status_atual:
                conn.rollback()
                return False
            if status not in TRANSICOES_ENCOMENDA.get(status_atual, set()):
                raise ValueError("Transição de status não permitida.")

            cur.execute("""
                UPDATE encomendas
                SET status = %s,
                    data_resposta = CASE
                        WHEN %s IN ('morador_em_casa','retida_portaria') THEN CURRENT_TIMESTAMP
                        ELSE data_resposta END,
                    data_retirada = CASE WHEN %s = 'retirada' THEN CURRENT_TIMESTAMP ELSE data_retirada END,
                    retirado_por = CASE WHEN %s = 'retirada' THEN %s ELSE retirado_por END,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND condominio_id = %s AND status = %s
            """, (status, status, status, status, retirado_por or None, encomenda_id, tenant_id, status_atual))
            alterou = cur.rowcount > 0
            if alterou and usuario_id:
                registrar_auditoria_cursor(cur, "encomenda.status", usuario_id=usuario_id, condominio_id=tenant_id, entidade="encomenda", entidade_id=encomenda_id, detalhes={"status": status})
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
