import logging
import os
import uuid
import time
from flask import Flask, jsonify, session, redirect, url_for, request, g
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from routes.admin import admin_bp
from routes.platform_admin import platform_admin_bp
from routes.main import main_bp
from routes.visitantes import visitantes_bp
from routes.auth import auth_bp
from routes.moradores import moradores_bp
from routes.encomendas import encomendas_bp
from routes.entregadores import entregadores_bp
from database.connection import verificar_conexao
from utils.authz import load_identity

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.from_object(Config)
Config.validate()
csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_meta():
    from flask_wtf.csrf import generate_csrf
    return {"global_csrf_token": generate_csrf}


app.register_blueprint(main_bp)
app.register_blueprint(visitantes_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(platform_admin_bp)
app.register_blueprint(moradores_bp)
app.register_blueprint(encomendas_bp)
app.register_blueprint(entregadores_bp)

ROTAS_PUBLICAS = {"auth.login", "auth.logout", "static", "healthz", "readyz"}


@app.before_request
def verificar_login():
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    g.request_started_at = time.perf_counter()
    load_identity()
    endpoint = request.endpoint or ""
    if endpoint in ROTAS_PUBLICAS or endpoint.startswith("static"):
        return
    if not getattr(g, "current_user", None):
        return redirect(url_for("auth.login"))
    if g.current_user.get("nivel") == "platform_admin" and not endpoint.startswith("platform_admin."):
        return redirect(url_for("platform_admin.condominios"))


@app.after_request
def security_headers(response):
    started_at = getattr(g, "request_started_at", None)
    duration_ms = (time.perf_counter() - started_at) * 1000 if started_at is not None else None
    if request.endpoint != "static":
        app.logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            getattr(g, "request_id", None), request.method, request.path, response.status_code,
            duration_ms if duration_ms is not None else 0.0,
        )
    response.headers.setdefault("X-Request-ID", getattr(g, "request_id", uuid.uuid4().hex))
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if Config.APP_ENV == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.get("/readyz")
def readyz():
    try:
        return (jsonify(status="ready"), 200) if verificar_conexao() else (jsonify(status="not_ready"), 503)
    except Exception:
        app.logger.exception("Readiness database check failed")
        return jsonify(status="not_ready"), 503




@app.errorhandler(403)
def forbidden(_error):
    return jsonify(error="forbidden", request_id=getattr(g, "request_id", None)), 403


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="not_found", request_id=getattr(g, "request_id", None)), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error("Unhandled request error request_id=%s", getattr(g, "request_id", None), exc_info=error)
    return jsonify(error="internal_error", request_id=getattr(g, "request_id", None)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=Config.APP_ENV == "development")  # nosec B104 - container/dev bind; production uses gunicorn
