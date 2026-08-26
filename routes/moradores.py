import logging
from flask import Blueprint, render_template, request, redirect, flash, url_for, session

from database.models import (
    cadastrar_morador,
    listar_moradores,
    buscar_moradores,
    buscar_morador_por_id,
    atualizar_morador,
    inativar_morador,
    ativar_morador,
    cpf_morador_ja_cadastrado,
    listar_unidades,
    criar_unidade,
)
from utils.validators import limpar_cpf, validar_cpf

moradores_bp = Blueprint("moradores", __name__, url_prefix="/moradores")
logger = logging.getLogger(__name__)


def _admin_ou_funcionario():
    return session.get("usuario_tipo") in ("admin", "funcionario")


@moradores_bp.route("/")
def listar():
    termo = request.args.get("q", "").strip()
    dados = buscar_moradores(termo) if termo else listar_moradores()
    return render_template("moradores/lista.html", moradores=dados, termo=termo)


@moradores_bp.route("/novo", methods=["GET", "POST"])
def novo():
    unidades = listar_unidades()

    if request.method == "POST":
        nome       = request.form.get("nome", "").strip().upper()
        cpf        = limpar_cpf(request.form.get("cpf", ""))
        telefone   = request.form.get("telefone", "").strip()
        email      = request.form.get("email", "").strip().lower()
        unidade_id = request.form.get("unidade_id") or None
        observacao = request.form.get("observacao", "").strip()

        # Permitir criar unidade on-the-fly
        nova_unidade = request.form.get("nova_unidade", "").strip().upper()
        if nova_unidade and not unidade_id:
            resultado = criar_unidade(nova_unidade)
            if resultado:
                unidade_id = resultado["id"]

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
            cadastrar_morador(nome, cpf or None, telefone, email, unidade_id, observacao)
            flash("Morador cadastrado com sucesso!", "sucesso")
            return redirect(url_for("moradores.listar"))
        except Exception:
            logger.exception("Erro ao cadastrar morador")
            flash("Erro ao cadastrar morador.", "erro")
            return redirect(url_for("moradores.novo"))

    return render_template("moradores/form.html", morador=None, unidades=unidades, titulo="Novo Morador")


@moradores_bp.route("/<int:id>/editar", methods=["GET", "POST"])
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
        if nova_unidade and not unidade_id:
            resultado = criar_unidade(nova_unidade)
            if resultado:
                unidade_id = resultado["id"]

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
            atualizar_morador(id, nome, cpf or None, telefone, email, unidade_id, observacao)
            flash("Morador atualizado com sucesso!", "sucesso")
            return redirect(url_for("moradores.listar"))
        except Exception:
            logger.exception("Erro ao atualizar morador")
            flash("Erro ao atualizar morador.", "erro")
            return redirect(url_for("moradores.editar", id=id))

    return render_template("moradores/form.html", morador=morador, unidades=unidades, titulo="Editar Morador")


@moradores_bp.route("/<int:id>")
def detalhe(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))
    return render_template("moradores/detalhe.html", morador=morador)


@moradores_bp.route("/<int:id>/inativar", methods=["POST"])
def inativar(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))

    inativar_morador(id)
    flash(f"Morador {morador['nome']} inativado.", "sucesso")
    return redirect(url_for("moradores.listar"))


@moradores_bp.route("/<int:id>/ativar", methods=["POST"])
def ativar(id):
    morador = buscar_morador_por_id(id)
    if not morador:
        flash("Morador não encontrado.", "erro")
        return redirect(url_for("moradores.listar"))

    ativar_morador(id)
    flash(f"Morador {morador['nome']} reativado.", "sucesso")
    return redirect(url_for("moradores.listar"))
