from flask import Blueprint, render_template, request, redirect, session, flash, url_for
import hashlib
import logging
import time
from collections import defaultdict, deque

from database.models import buscar_usuario, buscar_platform_admin, verificar_senha

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)
_LOGIN_WINDOW = 15 * 60
_LOGIN_LIMIT = 10
_login_attempts = defaultdict(deque)


def _login_key():
    ip = request.remote_addr or "unknown"
    usuario = request.form.get("usuario", "").strip().lower()
    return hashlib.sha256(f"{ip}|{usuario}".encode()).hexdigest()


def _login_rate_limited():
    now = time.monotonic()
    bucket = _login_attempts[_login_key()]
    while bucket and now - bucket[0] > _LOGIN_WINDOW:
        bucket.popleft()
    return len(bucket) >= _LOGIN_LIMIT


def _record_failed_login():
    _login_attempts[_login_key()].append(time.monotonic())


def _clear_login_failures():
    _login_attempts.pop(_login_key(), None)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if _login_rate_limited():
            logger.warning("Login rate limit reached")
            flash("Muitas tentativas de acesso. Aguarde alguns minutos e tente novamente.", "erro")
            return redirect(url_for("auth.login"))
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
            _record_failed_login()
            flash("Usuário ou senha inválidos.", "erro")
            return redirect(url_for("auth.login"))

        _clear_login_failures()
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
