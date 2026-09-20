from flask import Blueprint, render_template, request, redirect, session, flash, url_for

from database.models import buscar_usuario, buscar_platform_admin, verificar_senha

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        if not usuario or not senha:
            flash("Preencha usuário e senha.", "erro")
            return redirect(url_for("auth.login"))

        user = buscar_platform_admin(usuario)
        is_platform_admin = bool(user)

        if not user:
            user = buscar_usuario(usuario)

        if not user or not verificar_senha(user, senha):
            flash("Usuário ou senha inválidos.", "erro")
            return redirect(url_for("auth.login"))

        session.clear()
        session["usuario_id"] = user["id"]
        session["usuario_nome"] = user["nome"]
        session["is_platform_admin"] = is_platform_admin
        if is_platform_admin:
            session["usuario_tipo"] = "platform_admin"
            session["condominio_id"] = None
            session.permanent = True
            flash("Login realizado com sucesso!", "sucesso")
            return redirect(url_for("platform_admin.condominios"))

        session["usuario_tipo"] = user["nivel"]
        session["condominio_id"] = user.get("condominio_id")
        session.permanent = True
        flash("Login realizado com sucesso!", "sucesso")
        return redirect(url_for("main.index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("auth.login"))
