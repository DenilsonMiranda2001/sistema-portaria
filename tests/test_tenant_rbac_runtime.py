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
