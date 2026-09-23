from flask import Blueprint, render_template, request, redirect, flash, url_for, session, g
from utils.authz import roles_required
from utils.audit import registrar_auditoria

from database.models import (
    criar_usuario,
    listar_usuarios,
    buscar_usuario_por_id,
    atualizar_usuario,
    inativar_usuario,
    ativar_usuario,
    atualizar_senha_usuario,
    resumo_unidades,
    listar_auditoria_tenant
)

admin_bp = Blueprint("admin", __name__)

def admin_obrigatorio():
    return bool(getattr(g, "current_user", None) and g.current_user.get("nivel") == "admin_condominio")


@admin_bp.route("/usuarios", methods=["GET", "POST"])
@roles_required("admin_condominio")
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

        if tipo not in ("admin_condominio", "administrativo", "porteiro"):
            flash("Perfil de usuário inválido.", "erro")
            return redirect(url_for("admin.usuarios"))

        resultado = criar_usuario(nome, usuario, senha, tipo, session["usuario_id"])

        if resultado == "existe":
            flash("Já existe um usuário com esse login.", "erro")
        else:
            flash("Usuário criado com sucesso!", "sucesso")

        return redirect(url_for("admin.usuarios"))

    dados = listar_usuarios()
    residencial = resumo_unidades()
    resumo_equipe = {
        "total": len(dados),
        "ativos": sum(bool(u["ativo"]) for u in dados),
        "administradores": sum(bool(u["ativo"]) and u["nivel"] == "admin_condominio" for u in dados),
        "administrativos": sum(bool(u["ativo"]) and u["nivel"] == "administrativo" for u in dados),
        "porteiros": sum(bool(u["ativo"]) and u["nivel"] == "porteiro" for u in dados),
    }
    return render_template("usuarios.html", usuarios=dados, residencial=residencial, resumo_equipe=resumo_equipe)


@admin_bp.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@roles_required("admin_condominio")
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

        if tipo not in ("admin_condominio", "administrativo", "porteiro"):
            flash("Perfil de usuário inválido.", "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        if id == session["usuario_id"] and tipo != "admin_condominio":
            flash("Você não pode remover seu próprio acesso de administrador.", "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        try:
            resultado = atualizar_usuario(id, nome, usuario, tipo, session["usuario_id"])
        except ValueError as exc:
            flash(str(exc), "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        if resultado == "existe":
            flash("Já existe outro usuário com esse login.", "erro")
            return redirect(url_for("admin.editar_usuario", id=id))

        flash("Usuário atualizado com sucesso!", "sucesso")
        return redirect(url_for("admin.usuarios"))

    return render_template("editar_usuario.html", user=user)


@admin_bp.route("/usuarios/inativar/<int:id>", methods=["POST"])
@roles_required("admin_condominio")
def inativar_usuario_rota(id):

    if session.get("usuario_id") == id:
        flash("Você não pode inativar seu próprio usuário.", "erro")
        return redirect(url_for("admin.usuarios"))

    user = buscar_usuario_por_id(id, exigir_tenant=True)
    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    try:
        alterou = inativar_usuario(id, session["usuario_id"])
        if alterou:
            flash("Usuário inativado com sucesso!", "sucesso")
    except ValueError as exc:
        flash(str(exc), "erro")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/ativar/<int:id>", methods=["POST"])
@roles_required("admin_condominio")
def ativar_usuario_rota(id):

    user = buscar_usuario_por_id(id, exigir_tenant=True)
    if not user:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios"))

    alterou = ativar_usuario(id, session["usuario_id"])
    flash("Usuário ativado com sucesso!" if alterou else "Usuário já estava ativo.", "sucesso" if alterou else "aviso")
    return redirect(url_for("admin.usuarios"))

@admin_bp.route("/usuarios/senha/<int:id>", methods=["GET", "POST"])
@roles_required("admin_condominio")
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

        alterou = atualizar_senha_usuario(id, nova_senha, session["usuario_id"])
        if not alterou:
            flash("Não foi possível atualizar a senha deste usuário.", "erro")
            return redirect(url_for("admin.alterar_senha_usuario", id=id))
        flash("Senha atualizada com sucesso!", "sucesso")
        return redirect(url_for("admin.usuarios"))

    return render_template("alterar_senha_usuario.html", user=user)

@admin_bp.route("/auditoria")
@roles_required("admin_condominio")
def auditoria():
    try:
        pagina = max(1, min(int(request.args.get("pagina", "1")), 1000))
    except (TypeError, ValueError):
        pagina = 1
    eventos = listar_auditoria_tenant(51, pagina=pagina)
    return render_template("auditoria.html", eventos=eventos[:50], pagina=pagina, tem_proxima=len(eventos) > 50)
