from flask import Blueprint, render_template, request, redirect, flash, url_for, session
from utils.authz import roles_required
from utils.audit import registrar_auditoria

from database.models import (
    criar_usuario,
    listar_usuarios,
    buscar_usuario_por_id,
    atualizar_usuario,
    inativar_usuario,
    ativar_usuario,
    atualizar_senha_usuario
)

admin_bp = Blueprint("admin", __name__)

def admin_obrigatorio():
    return session.get("usuario_tipo") == "admin"


@admin_bp.route("/usuarios", methods=["GET", "POST"])
@roles_required("admin")
def usuarios():

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()
        tipo = request.form.get("tipo", "").strip().lower()

        if not nome or not usuario or not senha:
            flash("Preencha nome, usuário e senha.", "erro")
            return redirect(url_for("admin.usuarios"))
        if len(senha) < 12:
            flash("A senha deve ter pelo menos 12 caracteres.", "erro")
            return redirect(url_for("admin.usuarios"))

        if tipo not in ["admin", "funcionario"]:
            tipo = "funcionario"

        resultado = criar_usuario(nome, usuario, senha, tipo)

        if resultado == "existe":
            flash("Já existe um usuário com esse login.", "erro")
        else:
            registrar_auditoria("usuario.criado", usuario_id=session["usuario_id"], condominio_id=session["condominio_id"], entidade="usuario", entidade_id=resultado["id"], detalhes={"nivel": tipo})
            flash("Usuário criado com sucesso!", "sucesso")

        return redirect(url_for("admin.usuarios"))

    dados = listar_usuarios()
    return render_template("usuarios.html", usuarios=dados)


@admin_bp.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@roles_required("admin")
def editar_usuario(id):

    user = buscar_usuario_por_id(id, exigir_tenant=True)

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        usuario = request.form.get("usuario", "").strip()
        tipo = request.form.get("tipo", "").strip().lower()

        if not nome or not usuario:
            flash("Preencha nome e usuário.", "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        if tipo not in ["admin", "funcionario"]:
            tipo = "funcionario"

        resultado = atualizar_usuario(id, nome, usuario, tipo)

        if resultado == "existe":
            flash("Já existe outro usuário com esse login.", "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        registrar_auditoria("usuario.atualizado", usuario_id=session["usuario_id"], condominio_id=session["condominio_id"], entidade="usuario", entidade_id=id, detalhes={"nivel": tipo})
        flash("Usuário atualizado com sucesso!", "sucesso")
        return redirect(url_for("admin.usuarios"))

    return render_template("editar_usuario.html", user=user)


@admin_bp.route("/usuarios/inativar/<int:id>", methods=["POST"])
@roles_required("admin")
def inativar_usuario_rota(id):

    if session.get("usuario_id") == id:
        flash("Você não pode inativar seu próprio usuário.", "erro")
        return redirect(url_for("admin.usuarios"))

    user = buscar_usuario_por_id(id, exigir_tenant=True)
    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    inativar_usuario(id)
    registrar_auditoria("usuario.inativado", usuario_id=session["usuario_id"], condominio_id=session["condominio_id"], entidade="usuario", entidade_id=id)
    flash("Usuário inativado com sucesso!", "sucesso")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/ativar/<int:id>", methods=["POST"])
@roles_required("admin")
def ativar_usuario_rota(id):

    user = buscar_usuario_por_id(id, exigir_tenant=True)
    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    ativar_usuario(id)
    registrar_auditoria("usuario.ativado", usuario_id=session["usuario_id"], condominio_id=session["condominio_id"], entidade="usuario", entidade_id=id)
    flash("Usuário ativado com sucesso!", "sucesso")
    return redirect(url_for("admin.usuarios"))

@admin_bp.route("/usuarios/senha/<int:id>", methods=["GET", "POST"])
@roles_required("admin")
def alterar_senha_usuario(id):

    user = buscar_usuario_por_id(id, exigir_tenant=True)

    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    if request.method == "POST":
        nova_senha = request.form.get("nova_senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()

        if not nova_senha or not confirmar_senha:
            flash("Preencha os dois campos de senha.", "erro")
            return redirect(url_for("admin.alterar_senha_usuario", id=id))

        if nova_senha != confirmar_senha:
            flash("As senhas não coincidem.", "erro")
            return redirect(url_for("admin.alterar_senha_usuario", id=id))
        if len(nova_senha) < 12:
            flash("A senha deve ter pelo menos 12 caracteres.", "erro")
            return redirect(url_for("admin.alterar_senha_usuario", id=id))

        atualizar_senha_usuario(id, nova_senha)
        registrar_auditoria("usuario.senha_alterada", usuario_id=session["usuario_id"], condominio_id=session["condominio_id"], entidade="usuario", entidade_id=id)
        flash("Senha atualizada com sucesso!", "sucesso")
        return redirect(url_for("admin.usuarios"))

    return render_template("alterar_senha_usuario.html", user=user)