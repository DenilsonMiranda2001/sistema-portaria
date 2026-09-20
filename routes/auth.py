from flask import Blueprint, render_template, request, redirect, session, flash, url_for

from database.models import buscar_usuario, verificar_senha

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        condominio_slug = request.form.get("condominio", "").strip().lower()
        condominio_slug = request.form.get("condominio", "").strip().lower()

        if not usuario or not senha or not condominio_slug:
            flash("Preencha condomínio, usuário e senha.", "erro")
            return redirect(url_for("auth.login"))

        user = buscar_usuario(usuario, condominio_slug)

        # Keep authentication failures intentionally indistinguishable.
        if not user or not verificar_senha(user, senha):
            flash("Usuário ou senha inválidos.", "erro")
            return redirect(url_for("auth.login"))

        session.clear()
        session["usuario_id"] = user["id"]
        session["usuario_nome"] = user["nome"]
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
