import logging
import os
from flask import Flask, jsonify, session, redirect, url_for, request, g
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from routes.admin import admin_bp
from routes.main import main_bp
from routes.visitantes import visitantes_bp
from routes.auth import auth_bp
from routes.moradores import moradores_bp
from routes.encomendas import encomendas_bp
from database.models import criar_tabelas
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

# Temporary compatibility gate: schema bootstrap remains enabled outside
# production while migrations are introduced. Production must run migrations
# explicitly before starting the web process.
if Config.APP_ENV != "production":
    criar_tabelas()

app.register_blueprint(main_bp)
app.register_blueprint(visitantes_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(moradores_bp)
app.register_blueprint(encomendas_bp)

ROTAS_PUBLICAS = {"auth.login", "auth.logout", "static", "healthz", "readyz"}


@app.before_request
def verificar_login():
    load_identity()
    endpoint = request.endpoint or ""
    if endpoint in ROTAS_PUBLICAS or endpoint.startswith("static"):
        return
    if not getattr(g, "current_user", None):
        return redirect(url_for("auth.login"))


@app.after_request
def security_headers(response):
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=Config.APP_ENV == "development")
