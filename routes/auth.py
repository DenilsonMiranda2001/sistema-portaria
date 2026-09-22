from flask import Blueprint, render_template, request, redirect, session, flash, url_for
import hashlib
import logging


from database.models import buscar_usuario, buscar_platform_admin, verificar_senha
from database.connection import conectar, liberar

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)
LOGIN_WINDOW_MINUTES = 15
LOGIN_LIMIT = 10
LOGIN_IP_LIMIT = 30


def _login_key():
    ip = request.remote_addr or "unknown"
    usuario = request.form.get("usuario", "").strip().lower()
    return hashlib.sha256(f"user|{ip}|{usuario}".encode()).hexdigest()


def _login_ip_key():
    ip = request.remote_addr or "unknown"
    return hashlib.sha256(f"ip|{ip}".encode()).hexdigest()


def _login_rate_limited():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_attempts WHERE janela_inicio < CURRENT_TIMESTAMP - INTERVAL '2 days'")
            cur.execute("""SELECT bloqueado_ate > CURRENT_TIMESTAMP AS bloqueado
                           FROM login_attempts WHERE chave IN (%s, %s)
                           ORDER BY bloqueado_ate DESC NULLS LAST LIMIT 1""", (_login_key(), _login_ip_key()))
            row = cur.fetchone()
        conn.commit()
        return bool(row and row["bloqueado"])
    except Exception:
        conn.rollback()
        logger.exception("Failed to evaluate login rate limit")
        return True
    finally:
        liberar(conn)


def _record_failed_login():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            statement = """
                INSERT INTO login_attempts(chave,tentativas,janela_inicio,bloqueado_ate)
                VALUES(%s,1,CURRENT_TIMESTAMP,NULL)
                ON CONFLICT(chave) DO UPDATE SET
                    tentativas = CASE
                        WHEN login_attempts.janela_inicio < CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN 1
                        ELSE login_attempts.tentativas + 1 END,
                    janela_inicio = CASE
                        WHEN login_attempts.janela_inicio < CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN CURRENT_TIMESTAMP
                        ELSE login_attempts.janela_inicio END,
                    bloqueado_ate = CASE
                        WHEN (CASE WHEN login_attempts.janela_inicio < CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN 1 ELSE login_attempts.tentativas + 1 END) >= %s
                        THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes'
                        ELSE login_attempts.bloqueado_ate END
            """
            cur.execute(statement, (_login_key(), LOGIN_LIMIT))
            cur.execute(statement, (_login_ip_key(), LOGIN_IP_LIMIT))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed to persist login attempt")
    finally:
        liberar(conn)


def _clear_login_failures():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_attempts WHERE chave=%s", (_login_key(),))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed to clear login attempts")
    finally:
        liberar(conn)


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
