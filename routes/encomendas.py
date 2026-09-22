import logging
import re
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from database.encomendas import (
    adicionar_encomenda,
    atualizar_status_encomenda,
    atualizar_status_lote,
    buscar_encomenda,
    buscar_lote,
    criar_lote,
    listar_encomendas,
    listar_encomendas_lote,
    listar_lotes,
    resumo_painel,
)
from database.models import listar_moradores
from database.entregadores import listar_entregadores
from utils.audit import registrar_auditoria
from utils.authz import roles_required


encomendas_bp = Blueprint("encomendas", __name__, url_prefix="/encomendas")
logger = logging.getLogger(__name__)
TRANSPORTADORAS = ("Shopee", "Mercado Livre", "Correios", "Amazon", "Outra")


def _voltar_padrao():
    destino = request.form.get("proximo", "")
    if destino == "retidas":
        return url_for("encomendas.retidas")
    return url_for("encomendas.painel")


def _whatsapp(encomenda):
    telefone = re.sub(r"\D", "", encomenda.get("telefone") or "")
    if not telefone:
        return None
    if len(telefone) in (10, 11):
        telefone = f"55{telefone}"
    data = encomenda["data_chegada"].strftime("%d/%m/%Y %H:%M")
    mensagem = (
        f"Olá, chegou uma encomenda para sua unidade na portaria.\n\n"
        f"Código de retirada: {encomenda['codigo_retirada']}\n"
        f"Transportadora: {encomenda['transportadora']}\n"
        f"Data/hora: {data}\n\n"
        "A encomenda foi recebida e está disponível para retirada no ponto de encomendas do condomínio."
    )
    return f"https://wa.me/{telefone}?text={quote(mensagem)}"


def _adicionar_links_whatsapp(encomendas):
    for encomenda in encomendas:
        encomenda["whatsapp_url"] = _whatsapp(encomenda)
    return encomendas


@encomendas_bp.route("/")
@roles_required("admin", "funcionario")
def painel():
    filtro = request.args.get("filtro", "hoje")
    termo = request.args.get("q", "").strip()
    lote_id = request.args.get("lote_id", type=int)
    transportadora = request.args.get("transportadora", "").strip()
    dados = listar_encomendas(filtro, termo, lote_id, transportadora)
    return render_template(
        "encomendas/painel.html",
        encomendas=_adicionar_links_whatsapp(dados),
        resumo=resumo_painel(),
        lotes=listar_lotes(),
        transportadoras=TRANSPORTADORAS,
        filtro=filtro,
        termo=termo,
        lote_id=lote_id,
        transportadora=transportadora,
    )


@encomendas_bp.route("/lotes")
@roles_required("admin", "funcionario")
def lotes():
    return render_template("encomendas/lotes.html", lotes=listar_lotes())


@encomendas_bp.route("/lotes/novo", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def novo_lote():
    if request.method == "POST":
        transportadora = request.form.get("transportadora", "").strip()
        if transportadora not in TRANSPORTADORAS:
            flash("Selecione uma transportadora válida.", "erro")
            return redirect(url_for("encomendas.novo_lote"))
        try:
            lote_id = criar_lote(
                request.form.get("nome_entregador"),
                transportadora,
                request.form.get("observacao"),
                session["usuario_id"],
                request.form.get("entregador_id", type=int),
            )
            flash("Lote criado. Cadastre as encomendas em sequência.", "sucesso")
            return redirect(url_for("encomendas.lote_detalhe", lote_id=lote_id))
        except Exception:
            logger.exception("Erro ao criar lote de encomendas")
            flash("Não foi possível criar o lote.", "erro")
            return redirect(url_for("encomendas.novo_lote"))
    return render_template("encomendas/novo_lote.html", transportadoras=TRANSPORTADORAS, entregadores=listar_entregadores(apenas_ativos=True))


@encomendas_bp.route("/lotes/<int:lote_id>", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def lote_detalhe(lote_id):
    lote = buscar_lote(lote_id)
    if not lote:
        flash("Lote não encontrado.", "erro")
        return redirect(url_for("encomendas.lotes"))

    if request.method == "POST":
        if lote["status"] in ("concluido", "cancelado"):
            flash("Este lote está encerrado e não aceita novas encomendas.", "aviso")
            return redirect(url_for("encomendas.lote_detalhe", lote_id=lote_id))
        try:
            nova = adicionar_encomenda(
                lote_id,
                request.form.get("morador_id", type=int),
                request.form.get("unidade"),
                request.form.get("nome_morador"),
                request.form.get("codigo_rastreio"),
                request.form.get("descricao"),
                request.form.get("observacao"),
                session["usuario_id"],
            )
            flash(f"Encomenda {nova['codigo_retirada']} adicionada.", "sucesso")
        except ValueError as exc:
            flash(str(exc), "erro")
        except Exception:
            logger.exception("Erro ao adicionar encomenda")
            flash("Não foi possível adicionar a encomenda.", "erro")
        return redirect(url_for("encomendas.lote_detalhe", lote_id=lote_id))

    moradores = listar_moradores()
    itens = _adicionar_links_whatsapp(listar_encomendas_lote(lote_id))
    return render_template(
        "encomendas/lote_detalhe.html", lote=lote, encomendas=itens, moradores=moradores
    )


@encomendas_bp.route("/lotes/<int:lote_id>/status", methods=["POST"])
@roles_required("admin", "funcionario")
def status_lote(lote_id):
    status = request.form.get("status", "")
    try:
        alterou = atualizar_status_lote(lote_id, status, session["usuario_id"])
        flash("Status do recebimento atualizado." if alterou else "Recebimento ou status inválido.", "sucesso" if alterou else "erro")
    except ValueError as exc:
        flash(str(exc), "erro")
    except Exception:
        logger.exception("Erro ao atualizar status do recebimento")
        flash("Não foi possível atualizar o recebimento.", "erro")
    return redirect(url_for("encomendas.lote_detalhe", lote_id=lote_id))


@encomendas_bp.route("/<int:encomenda_id>/status", methods=["POST"])
@roles_required("admin", "funcionario")
def status_encomenda(encomenda_id):
    encomenda = buscar_encomenda(encomenda_id)
    if not encomenda:
        flash("Encomenda não encontrada.", "erro")
        return redirect(_voltar_padrao())
    try:
        alterou = atualizar_status_encomenda(
            encomenda_id, request.form.get("status", ""), request.form.get("retirado_por"), session["usuario_id"]
        )
        if alterou:
            flash("Status da encomenda atualizado.", "sucesso")
        else:
            flash("A encomenda já está encerrada e não pode ser alterada.", "aviso")
    except ValueError as exc:
        flash(str(exc), "erro")
    except Exception:
        logger.exception("Erro ao atualizar status da encomenda")
        flash("Não foi possível atualizar a encomenda.", "erro")
    destino = request.form.get("proximo")
    if destino == "lote":
        return redirect(url_for("encomendas.lote_detalhe", lote_id=encomenda["lote_id"]))
    return redirect(_voltar_padrao())


@encomendas_bp.route("/retidas")
@roles_required("admin", "funcionario")
def retidas():
    termo = request.args.get("q", "").strip()
    dados = listar_encomendas("retidas", termo)
    return render_template(
        "encomendas/retidas.html",
        encomendas=_adicionar_links_whatsapp(dados),
        termo=termo,
    )


@encomendas_bp.route("/historico")
@roles_required("admin", "funcionario")
def historico():
    termo = request.args.get("q", "").strip()
    dados = listar_encomendas("historico", termo)
    return render_template("encomendas/historico.html", encomendas=dados, termo=termo)
