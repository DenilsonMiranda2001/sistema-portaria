import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from psycopg2 import errors

from database.entregadores import (
    atualizar_entregador,
    buscar_entregador,
    criar_entregador,
    definir_status_entregador,
    listar_entregadores,
)
from routes.encomendas import TRANSPORTADORAS
from utils.authz import roles_required


entregadores_bp = Blueprint("entregadores", __name__, url_prefix="/entregadores")
logger = logging.getLogger(__name__)


@entregadores_bp.route("/")
@roles_required("admin", "funcionario")
def listar():
    return render_template("entregadores/lista.html", entregadores=listar_entregadores())


@entregadores_bp.route("/novo", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def novo():
    if request.method == "POST":
        try:
            entregador_id = criar_entregador(
                request.form.get("nome"), request.form.get("documento"),
                request.form.get("telefone"), request.form.get("transportadora"),
                session["usuario_id"],
            )
            flash("Entregador cadastrado com sucesso.", "sucesso")
            return redirect(url_for("entregadores.editar", entregador_id=entregador_id))
        except errors.UniqueViolation:
            flash("Já existe um entregador com esse documento neste condomínio.", "erro")
        except ValueError as exc:
            flash(str(exc), "erro")
        except Exception:
            logger.exception("Erro ao cadastrar entregador")
            flash("Não foi possível cadastrar o entregador.", "erro")
    return render_template("entregadores/form.html", entregador=None, transportadoras=TRANSPORTADORAS)


@entregadores_bp.route("/<int:entregador_id>/editar", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def editar(entregador_id):
    entregador = buscar_entregador(entregador_id)
    if not entregador:
        flash("Entregador não encontrado.", "erro")
        return redirect(url_for("entregadores.listar"))
    if request.method == "POST":
        try:
            atualizar_entregador(
                entregador_id, request.form.get("nome"), request.form.get("documento"),
                request.form.get("telefone"), request.form.get("transportadora"),
                session["usuario_id"],
            )
            flash("Entregador atualizado.", "sucesso")
            return redirect(url_for("entregadores.editar", entregador_id=entregador_id))
        except errors.UniqueViolation:
            flash("Já existe um entregador com esse documento neste condomínio.", "erro")
        except ValueError as exc:
            flash(str(exc), "erro")
        except Exception:
            logger.exception("Erro ao atualizar entregador")
            flash("Não foi possível atualizar o entregador.", "erro")
        entregador = buscar_entregador(entregador_id)
    return render_template("entregadores/form.html", entregador=entregador, transportadoras=TRANSPORTADORAS)


@entregadores_bp.route("/<int:entregador_id>/status", methods=["POST"])
@roles_required("admin")
def status(entregador_id):
    entregador = buscar_entregador(entregador_id)
    if not entregador:
        flash("Entregador não encontrado.", "erro")
        return redirect(url_for("entregadores.listar"))
    ativo = request.form.get("ativo") == "1"
    try:
        alterou = definir_status_entregador(entregador_id, ativo, session["usuario_id"])
        flash("Status do entregador atualizado." if alterou else "O entregador já estava nesse status.", "sucesso" if alterou else "aviso")
    except Exception:
        logger.exception("Erro ao alterar status do entregador")
        flash("Não foi possível alterar o status do entregador.", "erro")
    return redirect(url_for("entregadores.listar"))
