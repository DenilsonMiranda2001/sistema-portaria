"""Authenticated tenant/RBAC smoke against the isolated CI PostgreSQL database.

Run only against a disposable database after all migrations. Never point at production.
"""
import os
from uuid import uuid4

from werkzeug.security import generate_password_hash

from database.connection import conectar_dedicado
from app import app


def assert_status(response, expected, context):
    assert response.status_code == expected, (
        f"{context}: expected {expected}, got {response.status_code}"
    )


def main():
    assert os.getenv("APP_ENV") == "test", "Refusing to seed outside APP_ENV=test"
    assert "portaria_ci" in os.environ.get("DATABASE_URL", ""), "Disposable CI database required"
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

    assert_status(client.get(f"/foto/{visitors[1]}"), 404, "foreign visitor photo")
    assert_status(client.get(f"/historico/{visitors[1]}"), 302, "foreign visitor history")
    assert_status(client.get(f"/encomendas/lotes/{lots[1]}"), 302, "foreign parcel lot")
    assert_status(client.post(f"/encomendas/lotes/{lots[1]}/status",
                              data={"status": "concluido"}), 302, "foreign lot mutation")
    assert_status(client.get("/usuarios"), 200, "tenant admin user management")

    conn = conectar_dedicado("ci-smoke-check")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM lotes_encomendas WHERE id=%s", (lots[1],))
            assert cur.fetchone()["status"] == "aberto", "Cross-tenant lot was modified"
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
    print("Authenticated multi-tenant/RBAC smoke passed on disposable PostgreSQL")


if __name__ == "__main__":
    main()
