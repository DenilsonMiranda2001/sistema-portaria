import secrets
import string
from datetime import datetime

from database.connection import conectar, liberar


STATUS_FINAIS = ("retirada", "entregue_na_porta", "cancelada")
STATUS_PENDENTES = ("recebida", "aguardando_resposta", "morador_em_casa", "retida_portaria")


def _codigo_retirada(cur):
    alfabeto = string.ascii_uppercase + string.digits
    ano = datetime.now().year
    for _ in range(20):
        codigo = f"ENC-{ano}-{''.join(secrets.choice(alfabeto) for _ in range(4))}"
        cur.execute("SELECT 1 FROM encomendas WHERE codigo_retirada = %s", (codigo,))
        if not cur.fetchone():
            return codigo
    raise RuntimeError("Não foi possível gerar um código de retirada único.")


def criar_lote(nome_entregador, transportadora, observacao, usuario_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lotes_encomendas
                    (nome_entregador, transportadora, observacao, usuario_criacao_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                (nome_entregador or "").strip().upper() or None,
                (transportadora or "").strip(),
                (observacao or "").strip() or None,
                usuario_id,
            ))
            lote = cur.fetchone()
        conn.commit()
        return lote["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def buscar_lote(lote_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.*, COUNT(e.id)::int AS total_encomendas
                FROM lotes_encomendas l
                LEFT JOIN encomendas e ON e.lote_id = l.id
                WHERE l.id = %s
                GROUP BY l.id
            """, (lote_id,))
            return cur.fetchone()
    finally:
        liberar(conn)


def listar_lotes():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.*,
                       COUNT(e.id)::int AS total,
                       COUNT(e.id) FILTER (WHERE e.status IN
                           ('recebida','aguardando_resposta','morador_em_casa'))::int AS pendentes,
                       COUNT(e.id) FILTER (WHERE e.status = 'retida_portaria')::int AS retidas,
                       COUNT(e.id) FILTER (WHERE e.status = 'retirada')::int AS retiradas
                FROM lotes_encomendas l
                LEFT JOIN encomendas e ON e.lote_id = l.id
                GROUP BY l.id
                ORDER BY l.data_chegada DESC, l.id DESC
            """)
            return cur.fetchall()
    finally:
        liberar(conn)


def atualizar_status_lote(lote_id, status):
    if status not in ("concluido", "cancelado"):
        return False
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE lotes_encomendas SET status = %s
                WHERE id = %s AND status IN ('aberto', 'em_triagem')
            """, (status, lote_id))
            alterou = cur.rowcount > 0
            if alterou and status == "cancelado":
                cur.execute("""
                    UPDATE encomendas
                    SET status = 'cancelada', atualizado_em = CURRENT_TIMESTAMP
                    WHERE lote_id = %s
                      AND status NOT IN ('retirada', 'entregue_na_porta', 'cancelada')
                """, (lote_id,))
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def adicionar_encomenda(lote_id, morador_id, unidade, nome_morador,
                        codigo_rastreio, descricao, observacao, usuario_id):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            telefone = None
            unidade_id = None
            if morador_id:
                cur.execute("""
                    SELECT m.id, m.nome, m.telefone, m.unidade_id, u.codigo AS unidade
                    FROM moradores m
                    LEFT JOIN unidades u ON u.id = m.unidade_id
                    WHERE m.id = %s AND m.ativo = TRUE
                """, (morador_id,))
                morador = cur.fetchone()
                if not morador:
                    raise ValueError("Morador selecionado não foi encontrado.")
                nome_morador = morador["nome"]
                unidade = morador["unidade"] or unidade
                unidade_id = morador["unidade_id"]
                telefone = morador["telefone"]

            unidade = (unidade or "").strip().upper()
            if not unidade:
                raise ValueError("Informe a unidade da encomenda.")

            codigo = _codigo_retirada(cur)
            cur.execute("""
                INSERT INTO encomendas (
                    lote_id, morador_id, unidade_id, nome_morador, unidade,
                    codigo_rastreio, descricao, status, codigo_retirada,
                    observacao, usuario_criacao_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'aguardando_resposta',
                        %s, %s, %s)
                RETURNING id, codigo_retirada
            """, (
                lote_id, morador_id or None, unidade_id,
                (nome_morador or "").strip().upper() or None, unidade,
                (codigo_rastreio or "").strip().upper() or None,
                (descricao or "").strip() or None, codigo,
                (observacao or "").strip() or None, usuario_id,
            ))
            nova = cur.fetchone()
            cur.execute("""
                UPDATE lotes_encomendas SET status = 'em_triagem'
                WHERE id = %s AND status = 'aberto'
            """, (lote_id,))
        conn.commit()
        nova["telefone"] = telefone
        return nova
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)


def _select_encomendas(where="", order="e.data_chegada DESC, e.id DESC", params=()):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT e.*, l.transportadora, l.nome_entregador, l.status AS lote_status,
                       m.telefone
                FROM encomendas e
                JOIN lotes_encomendas l ON l.id = e.lote_id
                LEFT JOIN moradores m ON m.id = e.morador_id
                {where}
                ORDER BY {order}
            """, params)
            return cur.fetchall()
    finally:
        liberar(conn)


def listar_encomendas_lote(lote_id):
    return _select_encomendas("WHERE e.lote_id = %s", "e.id DESC", (lote_id,))


def buscar_encomenda(encomenda_id):
    dados = _select_encomendas("WHERE e.id = %s", params=(encomenda_id,))
    return dados[0] if dados else None


def listar_encomendas(filtro=None, termo=None, lote_id=None, transportadora=None):
    clausulas = []
    params = []
    if filtro == "hoje":
        clausulas.append("e.data_chegada::date = CURRENT_DATE")
    elif filtro == "pendentes":
        clausulas.append("e.status IN ('recebida','aguardando_resposta','morador_em_casa','retida_portaria')")
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
    where = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    return _select_encomendas(where, params=tuple(params))


def resumo_painel():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE data_chegada::date = CURRENT_DATE)::int AS recebidas_hoje,
                    COUNT(*) FILTER (WHERE status IN ('recebida','aguardando_resposta'))::int AS aguardando,
                    COUNT(*) FILTER (WHERE status = 'retida_portaria')::int AS retidas,
                    COUNT(*) FILTER (WHERE status = 'retirada'
                                      AND data_retirada::date = CURRENT_DATE)::int AS retiradas_hoje,
                    COUNT(*) FILTER (WHERE status = 'entregue_na_porta'
                                      AND atualizado_em::date = CURRENT_DATE)::int AS entregues_porta
                FROM encomendas
            """)
            return cur.fetchone()
    finally:
        liberar(conn)


def atualizar_status_encomenda(encomenda_id, status, retirado_por=None):
    permitidos = {
        "morador_em_casa", "retida_portaria", "entregue_na_porta",
        "retirada", "cancelada",
    }
    if status not in permitidos:
        raise ValueError("Status inválido.")
    retirado_por = (retirado_por or "").strip().upper()
    if status == "retirada" and not retirado_por:
        raise ValueError("Informe quem retirou a encomenda.")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE encomendas
                SET status = %s,
                    data_resposta = CASE
                        WHEN %s IN ('morador_em_casa','retida_portaria') THEN CURRENT_TIMESTAMP
                        ELSE data_resposta END,
                    data_retirada = CASE WHEN %s = 'retirada' THEN CURRENT_TIMESTAMP ELSE data_retirada END,
                    retirado_por = CASE WHEN %s = 'retirada' THEN %s ELSE retirado_por END,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s AND status <> 'cancelada'
                  AND status NOT IN ('retirada', 'entregue_na_porta')
            """, (status, status, status, status, retirado_por or None, encomenda_id))
            alterou = cur.rowcount > 0
        conn.commit()
        return alterou
    except Exception:
        conn.rollback()
        raise
    finally:
        liberar(conn)
