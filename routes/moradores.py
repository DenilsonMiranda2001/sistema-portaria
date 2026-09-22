import logging
from flask import Blueprint, render_template, request, redirect, flash, url_for, session

from database.models import (
    cadastrar_morador_com_unidade,
    listar_moradores,
    buscar_moradores,
    buscar_morador_por_id,
    atualizar_morador,
    inativar_morador,
    ativar_morador,
    cpf_morador_ja_cadastrado,
    listar_unidades,
)
from utils.validators import limpar_cpf, validar_cpf
from utils.audit import registrar_auditoria
from utils.authz import roles_required

moradores_bp = Blueprint("moradores", __name__, url_prefix="/moradores")
logger = logging.getLogger(__name__)


def _admin_ou_funcionario():
    return session.get("usuario_tipo") in ("admin", "funcionario")


@moradores_bp.route("/")
@roles_required("admin", "funcionario")
def listar():
    termo = request.args.get("q", "").strip()
    dados = buscar_moradores(termo) if termo else listar_moradores()
    return render_template("moradores/lista.html", moradores=dados, termo=termo)


@moradores_bp.route("/novo", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def novo():
    unidades = listar_unidades()

    if request.method == "POST":
        nome       = request.form.get("nome", "").strip().upper()
        cpf        = limpar_cpf(request.form.get("cpf", ""))
        telefone   = request.form.get("telefone", "").strip()
        email      = request.form.get("email", "").strip().lower()
        unidade_id = request.form.get("unidade_id") or None
        observacao = request.form.get("observacao", "").strip()

        nova_unidade = request.form.get("nova_unidade", "").strip().upper()

        if not nome:
            flash("Informe o nome do morador.", "erro")
            return redirect(url_for("moradores.novo"))

        if cpf:
            if not validar_cpf(cpf):
                flash("CPF inválido. Verifique os dígitos.", "erro")
                return redirect(url_for("moradores.novo"))
            existente = cpf_morador_ja_cadastrado(cpf)
            if existente:
                flash(f"CPF já cadastrado para: {existente['nome']}.", "erro")
                return redirect(url_for("moradores.novo"))

        try:
            morador_id = cadastrar_morador_com_unidade(nome, cpf or None, telefone, email, unidade_id, nova_unidade, observacao, session["usuario_id"])
            flash("Morador cadastrado com sucesso!", "sucesso")
            return redirect(url_for("moradores.listar"))
        except ValueError as exc:
            flash(str(exc), "erro")
            return redirect(url_for("moradores.novo"))
        except Exception:
            logger.exception("Erro ao cadastrar morador")
            flash("Erro ao cadastrar morador.", "erro")
            return redirect(url_for("moradores.novo"))

    return render_template("moradores/form.html", morador=None, unidades=unidades, titulo="Novo Morador")


@moradores_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@roles_required("admin", "funcionario")
def editar(id):
    morador  = buscar_morador_por_id(id)
    unidades = listar_unidades()

    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))

    if request.method == "POST":
        nome       = request.form.get("nome", "").strip().upper()
        cpf        = limpar_cpf(request.form.get("cpf", ""))
        telefone   = request.form.get("telefone", "").strip()
        email      = request.form.get("email", "").strip().lower()
        unidade_id = request.form.get("unidade_id") or None
        observacao = request.form.get("observacao", "").strip()

        nova_unidade = request.form.get("nova_unidade", "").strip().upper()

        if not nome:
            flash("Informe o nome do morador.", "erro")
            return redirect(url_for("moradores.editar", id=id))

        if cpf:
            if not validar_cpf(cpf):
                flash("CPF inválido.", "erro")
                return redirect(url_for("moradores.editar", id=id))
            existente = cpf_morador_ja_cadastrado(cpf, morador_id=id)
            if existente:
                flash(f"CPF já cadastrado para: {existente['nome']}.", "erro")
                return redirect(url_for("moradores.editar", id=id))

        try:
            atualizar_morador(id, nome, cpf or None, telefone, email, unidade_id, observacao, nova_unidade, session["usuario_id"])
            flash("Morador atualizado com sucesso!", "sucesso")
            return redirect(url_for("moradores.listar"))
        except ValueError as exc:
            flash(str(exc), "erro")
            return redirect(url_for("moradores.editar", id=id))
        except Exception:
            logger.exception("Erro ao atualizar morador")
            flash("Erro ao atualizar morador.", "erro")
            return redirect(url_for("moradores.editar", id=id))

    return render_template("moradores/form.html", morador=morador, unidades=unidades, titulo="Editar Morador")


@moradores_bp.route("/<int:id>")
@roles_required("admin", "funcionario")
def detalhe(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))
    return render_template("moradores/detalhe.html", morador=morador)


@moradores_bp.route("/<int:id>/inativar", methods=["POST"])
@roles_required("admin")
def inativar(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))

    alterou = inativar_morador(id, session["usuario_id"])
    flash(f"Morador {morador['nome']} inativado." if alterou else "Morador já estava inativo.", "sucesso" if alterou else "aviso")
    return redirect(url_for("moradores.listar"))


@moradores_bp.route("/<int:id>/ativar", methods=["POST"])
@roles_required("admin")
def ativar(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))

    alterou = ativar_morador(id, session["usuario_id"])
    flash(f"Morador {morador['nome']} reativado." if alterou else "Morador já estava ativo.", "sucesso" if alterou else "aviso")
    return redirect(url_for("moradores.listar"))
