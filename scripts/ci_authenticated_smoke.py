"""Authenticated tenant/RBAC smoke against the isolated CI PostgreSQL database.

Run only against a disposable database after all migrations. Never point at production.
"""
import os
from uuid import uuid4
from urllib.parse import urlparse

from werkzeug.security import generate_password_hash

from database.connection import conectar_dedicado
from app import app
from flask import g
from database.models import registrar_entrada, registrar_saida, atualizar_usuario, inativar_usuario
from database.encomendas import adicionar_encomenda, buscar_encomenda
from database.platform import definir_status_usuario_tenant


def assert_status(response, expected, context):
    assert response.status_code == expected, (
        f"{context}: expected {expected}, got {response.status_code}"
    )


def main():
    assert os.getenv("APP_ENV") == "test", "Refusing to seed outside APP_ENV=test"
    database_url = urlparse(os.environ.get("DATABASE_URL", ""))
    assert database_url.hostname in ("localhost", "127.0.0.1"), "Local CI database host required"
    assert database_url.path == "/portaria_ci", "Exact disposable CI database required"
    suffix = uuid4().hex[:10]
    password = "ci-authenticated-smoke-only"
    conn = conectar_dedicado("ci-authenticated-smoke")
    try:
        with conn.cursor() as cur:
            tenants = []
            users = []
            visitors = []
            lots = []
            for label in ("a", "b"):
                cur.execute(
                    "INSERT INTO condominios(nome,slug) VALUES (%s,%s) RETURNING id",
                    (f"Smoke {label}", f"smoke-{label}-{suffix}"),
                )
                tenant = cur.fetchone()["id"]
                tenants.append(tenant)
                cur.execute(
                    """INSERT INTO usuarios(condominio_id,nome,usuario,senha,nivel)
                       VALUES (%s,%s,%s,%s,'admin_condominio') RETURNING id""",
                    (tenant, f"Admin {label}", f"smoke-{label}-{suffix}",
                     generate_password_hash(password)),
                )
                users.append(cur.fetchone()["id"])
                cur.execute(
                    """INSERT INTO visitantes(condominio_id,nome,cpf)
                       VALUES (%s,%s,%s) RETURNING id""",
                    (tenant, f"Visitante {label}", "52998224725" if label == "a" else "11144477735"),
                )
                visitors.append(cur.fetchone()["id"])
                cur.execute(
                    """INSERT INTO lotes_encomendas(condominio_id,transportadora,usuario_criacao_id)
                       VALUES (%s,'CI',%s) RETURNING id""",
                    (tenant, users[-1]),
                )
                lots.append(cur.fetchone()["id"])
            cur.execute(
                """INSERT INTO usuarios(condominio_id,nome,usuario,senha,nivel)
                   VALUES (%s,'Porteiro CI',%s,%s,'porteiro') RETURNING id""",
                (tenants[0], f"smoke-porter-{suffix}", generate_password_hash(password)),
            )
            porter = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()

    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()

    # Real authentication and database-backed session identity.
    response = client.post("/login", data={"usuario": f"smoke-a-{suffix}", "senha": password})
    assert_status(response, 302, "tenant admin login")
    with client.session_transaction() as sess:
        assert sess["usuario_id"] == users[0]
        assert sess["condominio_id"] == tenants[0]
        assert sess["usuario_tipo"] == "admin_condominio"

    assert_status(client.get(f"/historico/{visitors[0]}"), 200, "own visitor history")
    assert_status(client.get(f"/encomendas/lotes/{lots[0]}"), 200, "own parcel lot")
    assert_status(client.get(f"/foto/{visitors[1]}"), 404, "foreign visitor photo")
    assert_status(client.get(f"/historico/{visitors[1]}"), 302, "foreign visitor history")
    foreign_lot_response = client.get(f"/encomendas/lotes/{lots[1]}")
    assert_status(foreign_lot_response, 302, "foreign parcel lot")
    assert "/encomendas/lotes" in foreign_lot_response.headers["Location"]
    assert_status(client.get(f"/encomendas/lotes/{lots[1]}"), 302, "foreign parcel lot")
    assert_status(client.post(f"/encomendas/lotes/{lots[1]}/status",
                              data={"status": "concluido"}), 302, "foreign lot mutation")
    assert_status(client.get("/usuarios"), 200, "tenant admin user management")

    # Stale or forged session tenant/role fields must not override database identity.
    with client.session_transaction() as sess:
        sess["condominio_id"] = tenants[1]
        sess["usuario_tipo"] = "platform_admin"
        sess["is_platform_admin"] = False
    assert_status(client.get("/usuarios"), 200, "database-backed admin identity despite stale session")
    assert_status(client.get(f"/encomendas/lotes/{lots[1]}"), 302,
                  "forged session tenant cannot access foreign lot")

    conn = conectar_dedicado("ci-smoke-check")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM lotes_encomendas WHERE id=%s", (lots[1],))
            assert cur.fetchone()["status"] == "aberto", "Cross-tenant lot was modified"
    finally:
        conn.close()

    # Exercise real domain writes and prove foreign-tenant identifiers cannot be used.
    with app.test_request_context("/"):
        g.tenant_id = tenants[0]
        visit_id = registrar_entrada(visitors[0], "UNIDADE CI", usuario_id=users[0])
        assert visit_id > 0
        try:
            registrar_entrada(visitors[1], "UNIDADE CI", usuario_id=users[0])
        except ValueError:
            pass
        else:
            raise AssertionError("Foreign-tenant visitor entry was accepted")
        assert registrar_saida(visitors[0], users[0]) is True
        parcel = adicionar_encomenda(lots[0], None, "CI-101", "DESTINATÁRIO CI",
                                     None, "PACOTE CI", None, users[0])
        assert buscar_encomenda(parcel["id"])["condominio_id"] == tenants[0]
        try:
            adicionar_encomenda(lots[1], None, "CI-101", "DESTINATÁRIO CI",
                                None, "PACOTE CI", None, users[0])
        except ValueError:
            pass
        else:
            raise AssertionError("Foreign-tenant parcel creation was accepted")

    # Protect the last active administrator through both demotion and deactivation.
    # The second tenant's administrator must not be manageable by tenant A.
    with app.test_request_context("/"):
        g.tenant_id = tenants[0]
        try:
            atualizar_usuario(users[0], "Admin A", f"smoke-a-{suffix}",
                              "porteiro", actor_id=users[0])
        except ValueError as exc:
            assert "administrador ativo" in str(exc)
        else:
            raise AssertionError("Last active tenant admin was demoted")
        try:
            inativar_usuario(users[0], actor_id=users[0])
        except ValueError as exc:
            assert "administrador ativo" in str(exc)
        else:
            raise AssertionError("Last active tenant admin was deactivated")
        assert inativar_usuario(users[1], actor_id=users[0]) is False
        assert atualizar_usuario(users[1], "Admin B", f"smoke-b-foreign-update-{suffix}",
                                 "porteiro", actor_id=users[0]) is False

    # The platform control plane must obey the same last-admin and tenant guards.
    try:
        definir_status_usuario_tenant(tenants[0], users[0], False)
    except ValueError as exc:
        assert "administrador ativo" in str(exc)
    else:
        raise AssertionError("Platform operation deactivated last tenant admin")
    assert definir_status_usuario_tenant(tenants[0], users[1], False) is False

    conn = conectar_dedicado("ci-smoke-admin-invariants")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT condominio_id,nivel,ativo FROM usuarios WHERE id=%s", (users[0],))
            admin_a = cur.fetchone()
            assert admin_a == {"condominio_id": tenants[0], "nivel": "admin_condominio",
                               "ativo": True}, admin_a
            cur.execute("SELECT condominio_id,nivel,ativo FROM usuarios WHERE id=%s", (users[1],))
            admin_b = cur.fetchone()
            assert admin_b == {"condominio_id": tenants[1], "nivel": "admin_condominio",
                               "ativo": True}, admin_b
    finally:
        conn.close()

    # Switching accounts must not retain the previous tenant or administrator privileges.
    assert_status(client.post("/logout"), 302, "logout")
    response = client.post("/login", data={
        "usuario": f"smoke-porter-{suffix}", "senha": password,
    })
    assert_status(response, 302, "porter login")
    with client.session_transaction() as sess:
        assert sess["usuario_id"] == porter
        assert sess["condominio_id"] == tenants[0]
        assert sess["usuario_tipo"] == "porteiro"
    assert_status(client.get("/usuarios"), 403, "porter administrator denial")
    assert_status(client.get(f"/encomendas/lotes/{lots[0]}"), 200,
                  "porter can access own tenant parcel lot")
    assert_status(client.get(f"/encomendas/lotes/{lots[1]}"), 302, "porter foreign lot denial")

    # A deactivated account must lose its existing session on its next request.
    conn = conectar_dedicado("ci-smoke-revoke")
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s", (porter,))
        conn.commit()
    finally:
        conn.close()
    assert_status(client.get("/usuarios"), 302, "deactivated account redirect")
    with client.session_transaction() as sess:
        assert "usuario_id" not in sess
    # A different tenant administrator must have legitimate access only to their tenant.
    other_client = app.test_client()
    response = other_client.post("/login", data={
        "usuario": f"smoke-b-{suffix}", "senha": password,
    })
    assert_status(response, 302, "second tenant admin login")
    with other_client.session_transaction() as sess:
        assert sess["usuario_id"] == users[1]
        assert sess["condominio_id"] == tenants[1]
        assert sess["usuario_tipo"] == "admin_condominio"
    assert_status(other_client.get(f"/encomendas/lotes/{lots[1]}"), 200,
                  "second tenant can access own parcel lot")
    assert_status(other_client.get(f"/encomendas/lotes/{lots[0]}"), 302,
                  "second tenant cannot access first tenant parcel lot")
    assert_status(other_client.get(f"/historico/{visitors[0]}"), 302,
                  "second tenant cannot access first tenant visitor history")
    assert_status(other_client.get("/usuarios"), 200,
                  "second tenant admin can access own user management")
    print("Authenticated multi-tenant/RBAC smoke passed on disposable PostgreSQL")


if __name__ == "__main__":
    main()
