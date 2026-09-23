"""Reception workflow regressions: server-side identity and authorization."""

import pytest
from flask import Flask, g, session
from werkzeug.exceptions import Forbidden

from routes import encomendas


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-only-reception-secret"
    app.register_blueprint(encomendas.encomendas_bp)
    return app


def _operator():
    g.current_user = {"id": 8, "nivel": "porteiro", "condominio_id": 17}
    g.tenant_id = 17
    session["usuario_id"] = 8


def test_quick_deliverer_registration_is_authorized_and_audited_through_model(app, monkeypatch):
    calls = []
    monkeypatch.setattr(encomendas, "criar_entregador", lambda *args: calls.append(args) or 44)
    with app.test_request_context("/encomendas/entregadores/rapido", method="POST", data={
        "nome": " Maria Silva ", "documento": "", "transportadora": "Correios",
    }):
        _operator()
        # Use an actual configured transportadora, independent of its display spelling.
        from routes.encomendas import TRANSPORTADORAS
        valid = next(value for value in TRANSPORTADORAS if value)
        from werkzeug.datastructures import ImmutableMultiDict
        request = __import__("flask").request
        request.form = ImmutableMultiDict({"nome": " Maria Silva ", "documento": "", "transportadora": valid})
        response, status = encomendas.cadastrar_entregador_rapido()
        assert status == 201
        assert response.get_json()["id"] == 44
        assert calls == [("Maria Silva", "", None, valid, 8)]


def test_quick_deliverer_registration_rejects_invalid_name_before_write(app, monkeypatch):
    calls = []
    monkeypatch.setattr(encomendas, "criar_entregador", lambda *args: calls.append(args))
    with app.test_request_context("/encomendas/entregadores/rapido", method="POST", data={
        "nome": "", "documento": "", "transportadora": "",
    }):
        _operator()
        response, status = encomendas.cadastrar_entregador_rapido()
        assert status == 400
        assert calls == []


def test_platform_admin_cannot_register_deliverer_in_tenant_reception(app, monkeypatch):
    monkeypatch.setattr(encomendas, "criar_entregador", lambda *args: pytest.fail("unauthorized write"))
    with app.test_request_context("/encomendas/entregadores/rapido", method="POST", data={
        "nome": "Person", "transportadora": "",
    }):
        g.current_user = {"id": 1, "nivel": "platform_admin"}
        with pytest.raises(Forbidden):
            encomendas.cadastrar_entregador_rapido()


def test_reception_requires_selected_deliverer_before_creating_lot(app, monkeypatch):
    monkeypatch.setattr(encomendas, "criar_lote", lambda *args: pytest.fail("lot without deliverer"))
    with app.test_request_context("/encomendas/lotes/novo", method="POST", data={
        "transportadora": "Correios", "nome_entregador": "Unverified",
    }):
        _operator()
        response = encomendas.novo_lote()
        assert response.status_code == 302
