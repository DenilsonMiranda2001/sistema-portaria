"""Executable authorization checks without requiring a live database."""

import pytest
from flask import Flask, g, session
from werkzeug.exceptions import Forbidden

from utils import authz


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    return app


@pytest.mark.parametrize("stored,expected", [
    ("admin", "admin_condominio"),
    ("funcionario", "porteiro"),
    ("administrativo", "administrativo"),
    ("porteiro", "porteiro"),
])
def test_legacy_role_identity_is_canonicalized(app, monkeypatch, stored, expected):
    monkeypatch.setattr(authz, "buscar_usuario_por_id", lambda user_id: {
        "id": user_id, "nivel": stored, "ativo": True,
        "condominio_id": 17, "condominio_ativo": True,
    })
    with app.test_request_context("/"):
        session["usuario_id"] = 9
        authz.load_identity()
        assert g.current_user["nivel"] == expected
        assert g.tenant_id == 17


@pytest.mark.parametrize("role,allowed", [
    ("admin_condominio", True),
    ("admin", True),
    ("administrativo", False),
    ("porteiro", False),
    ("platform_admin", False),
])
def test_tenant_admin_endpoint_is_server_side_restricted(app, role, allowed):
    protected = authz.roles_required("admin_condominio")(lambda: "ok")
    with app.test_request_context("/"):
        g.current_user = {"id": 1, "nivel": role}
        if allowed:
            assert protected() == "ok"
        else:
            with pytest.raises(Forbidden):
                protected()


def test_platform_admin_cannot_enter_tenant_operational_endpoint(app):
    protected = authz.roles_required("admin_condominio", "administrativo", "porteiro")(lambda: "ok")
    with app.test_request_context("/"):
        g.current_user = {"id": 1, "nivel": "platform_admin"}
        with pytest.raises(Forbidden):
            protected()


def test_inactive_tenant_identity_is_revoked(app, monkeypatch):
    monkeypatch.setattr(authz, "buscar_usuario_por_id", lambda user_id: {
        "id": user_id, "nivel": "admin_condominio", "ativo": True,
        "condominio_id": 17, "condominio_ativo": False,
    })
    with app.test_request_context("/"):
        session["usuario_id"] = 9
        authz.load_identity()
        assert g.current_user is None
        assert g.tenant_id is None
        assert "usuario_id" not in session


def test_platform_identity_does_not_inherit_tenant_context(app, monkeypatch):
    monkeypatch.setattr(authz, "buscar_platform_admin_por_id", lambda user_id: {
        "id": user_id, "nome": "Admin", "ativo": True,
    })
    with app.test_request_context("/"):
        session["usuario_id"] = 5
        session["is_platform_admin"] = True
        authz.load_identity()
        assert g.current_user["nivel"] == "platform_admin"
        assert g.tenant_id is None


def test_inactive_platform_admin_session_is_revoked(app, monkeypatch):
    monkeypatch.setattr(authz, "buscar_platform_admin_por_id", lambda user_id: {
        "id": user_id, "nome": "Admin", "ativo": False,
    })
    with app.test_request_context("/"):
        session["usuario_id"] = 5
        session["is_platform_admin"] = True
        authz.load_identity()
        assert g.current_user is None
        assert g.tenant_id is None
        assert "usuario_id" not in session
        assert "is_platform_admin" not in session


def test_platform_status_rejects_malformed_value_before_database_call(app, monkeypatch):
    from routes import platform_admin
    app.register_blueprint(platform_admin.platform_admin_bp)
    calls = []
    monkeypatch.setattr(platform_admin, "definir_status_condominio", lambda *args: calls.append(args))
    monkeypatch.setattr(platform_admin, "definir_status_usuario_tenant", lambda *args: calls.append(args))
    with app.test_request_context("/plataforma/condominios/7/status", method="POST", data={"ativo": "yes"}):
        g.current_user = {"id": 1, "nivel": "platform_admin"}
        session["usuario_id"] = 1
        from werkzeug.exceptions import BadRequest
        with pytest.raises(BadRequest):
            platform_admin.status_condominio(7)
    with app.test_request_context("/plataforma/condominios/7/usuarios/8/status", method="POST", data={}):
        g.current_user = {"id": 1, "nivel": "platform_admin"}
        session["usuario_id"] = 1
        with pytest.raises(BadRequest):
            platform_admin.status_usuario_condominio(7, 8)
    assert calls == []


def test_tenant_operator_cannot_use_platform_status_route(app):
    from routes import platform_admin
    app.register_blueprint(platform_admin.platform_admin_bp)
    with app.test_request_context("/plataforma/condominios/7/status", method="POST", data={"ativo": "0"}):
        g.current_user = {"id": 8, "nivel": "admin_condominio"}
        from werkzeug.exceptions import Forbidden
        with pytest.raises(Forbidden):
            platform_admin.status_condominio(7)


def test_tenant_user_creation_rejects_unknown_role_before_database_call(app, monkeypatch):
    from routes import admin
    app.register_blueprint(admin.admin_bp)
    calls = []
    monkeypatch.setattr(admin, "criar_usuario", lambda *args: calls.append(args))
    with app.test_request_context("/usuarios", method="POST", data={
        "nome": "Operador", "usuario": "operador", "senha": "senha-teste-12345", "tipo": "superuser",
    }):
        g.current_user = {"id": 2, "nivel": "admin_condominio"}
        session["usuario_id"] = 2
        response = admin.usuarios()
        assert response.status_code == 302
        assert response.location.endswith("/usuarios")
    assert calls == []


@pytest.mark.parametrize("role,tenant_id", [
    ("platform_admin", 17),
    ("superuser", 17),
    ("", 17),
    (None, 17),
    ("porteiro", None),
])
def test_invalid_tenant_identity_is_revoked_before_operational_routes(app, monkeypatch, role, tenant_id):
    monkeypatch.setattr(authz, "buscar_usuario_por_id", lambda user_id: {
        "id": user_id, "nivel": role, "ativo": True,
        "condominio_id": tenant_id, "condominio_ativo": True,
    })
    with app.test_request_context("/"):
        session["usuario_id"] = 9
        authz.load_identity()
        assert g.current_user is None
        assert g.tenant_id is None
        assert "usuario_id" not in session


@pytest.mark.parametrize("role,tenant_id", [("platform_admin", 17), ("unknown", 17), ("porteiro", None)])
def test_login_rejects_invalid_tenant_identity_without_session(app, monkeypatch, role, tenant_id):
    from routes import auth
    app.register_blueprint(auth.auth_bp)
    monkeypatch.setattr(auth, "_login_rate_limited", lambda: False)
    monkeypatch.setattr(auth, "_record_failed_login", lambda: None)
    monkeypatch.setattr(auth, "buscar_platform_admin", lambda login: None)
    monkeypatch.setattr(auth, "buscar_usuario", lambda login: {
        "id": 9, "nome": "Operador", "senha": "unused", "nivel": role,
        "ativo": True, "condominio_id": tenant_id,
    })
    monkeypatch.setattr(auth, "verificar_senha", lambda user, password: True)
    with app.test_request_context("/login", method="POST", data={"usuario": "operador", "senha": "valid"}):
        response = auth.login()
        assert response.status_code == 302
        assert response.location.endswith("/login")
        assert "usuario_id" not in session
        assert "is_platform_admin" not in session


def test_login_canonicalizes_legacy_tenant_role(app, monkeypatch):
    from routes import auth
    from routes.main import main_bp
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(main_bp)
    monkeypatch.setattr(auth, "_login_rate_limited", lambda: False)
    monkeypatch.setattr(auth, "_clear_login_failures", lambda: None)
    monkeypatch.setattr(auth, "buscar_platform_admin", lambda login: None)
    monkeypatch.setattr(auth, "buscar_usuario", lambda login: {
        "id": 9, "nome": "Operador", "senha": "unused", "nivel": "funcionario",
        "ativo": True, "condominio_id": 17,
    })
    monkeypatch.setattr(auth, "verificar_senha", lambda user, password: True)
    with app.test_request_context("/login", method="POST", data={"usuario": "operador", "senha": "valid"}):
        response = auth.login()
        assert response.status_code == 302
        assert session["usuario_id"] == 9
        assert session["usuario_tipo"] == "porteiro"
        assert session["condominio_id"] == 17
