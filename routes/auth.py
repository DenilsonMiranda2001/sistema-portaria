from flask import Blueprint, render_template, request, redirect, session, flash, url_for

from database.models import buscar_usuario, verificar_senha

auth_bp = Blueprint("auth", __name__)

# ==============================
# 🔐 LOGIN
# ==============================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()

        if not usuario or not senha:
            flash("Preencha usuário e senha.", "erro")
            return redirect(url_for("auth.login"))

        user = buscar_usuario(usuario)

        if not user:
            flash("Usuário não encontrado.", "erro")
            return redirect(url_for("auth.login"))

        if not verificar_senha(user, senha):
            flash("Senha incorreta.", "erro")
            return redirect(url_for("auth.login"))

        # CRIA SESSÃO
        session["usuario_id"] = user["id"]
        session["usuario_nome"] = user["nome"]
        session["usuario_tipo"] = user["nivel"]

        flash("Login realizado com sucesso!", "sucesso")
        return redirect(url_for("main.index"))

    return render_template("login.html")


# ==============================
# 🚪 LOGOUT
# ==============================
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("auth.login"))