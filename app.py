import logging
import os
from flask import Flask, session, redirect, url_for, request

from config import Config
from routes.admin import admin_bp
from routes.main import main_bp
from routes.visitantes import visitantes_bp
from routes.auth import auth_bp
from routes.moradores import moradores_bp
from routes.encomendas import encomendas_bp
from database.models import criar_tabelas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = os.path.join("static", "fotos")

criar_tabelas()

app.register_blueprint(main_bp)
app.register_blueprint(visitantes_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(moradores_bp)
app.register_blueprint(encomendas_bp)

ROTAS_PUBLICAS = {"auth.login", "auth.logout", "static"}

@app.before_request
def verificar_login():
    endpoint = request.endpoint or ""
    if endpoint in ROTAS_PUBLICAS or endpoint.startswith("static"):
        return
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
