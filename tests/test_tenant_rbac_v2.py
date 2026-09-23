from pathlib import Path


def test_tenant_rbac_migration_is_explicit_and_forward_only():
    sql = Path("migrations/0020_tenant_rbac_roles.sql").read_text(encoding="utf-8")
    assert "admin_condominio" in sql
    assert "administrativo" in sql
    assert "porteiro" in sql
    assert "UPDATE usuarios SET nivel = 'admin_condominio' WHERE nivel = 'admin'" in sql
    assert "UPDATE usuarios SET nivel = 'porteiro' WHERE nivel = 'funcionario'" in sql


def test_authz_canonicalizes_legacy_roles_during_rolling_deploy():
    source = Path("utils/authz.py").read_text(encoding="utf-8")
    assert '"admin": "admin_condominio"' in source
    assert '"funcionario": "porteiro"' in source
    assert "canonical_role" in source


def test_tenant_admin_is_only_role_that_manages_users():
    source = Path("routes/admin.py").read_text(encoding="utf-8")
    assert source.count('@roles_required("admin_condominio")') >= 6
    assert '"administrativo"' in source
    assert '"porteiro"' in source


def test_operational_roles_are_explicit():
    expected = '@roles_required("admin_condominio", "administrativo", "porteiro")'
    for path in ("routes/moradores.py", "routes/visitantes.py", "routes/encomendas.py", "routes/entregadores.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert expected in source


def test_last_active_tenant_admin_cannot_be_demoted():
    source = Path("database/models.py").read_text(encoding="utf-8")
    update = source[source.index("def atualizar_usuario("):source.index("def atualizar_senha_usuario(")]
    assert "FOR UPDATE" in update
    assert 'novo_nivel != "admin_condominio"' in update
    assert "O condomínio precisa manter pelo menos um administrador ativo." in update
    route = Path("routes/admin.py").read_text(encoding="utf-8")
    assert "except ValueError as exc:" in route


def test_new_install_schema_uses_tenant_roles():
    schema = Path("database/schema.sql").read_text(encoding="utf-8")
    assert "CHECK (nivel IN ('admin_condominio', 'administrativo', 'porteiro'))" in schema


def test_last_admin_mutations_serialize_on_tenant_row():
    models = Path("database/models.py").read_text(encoding="utf-8")
    platform = Path("database/platform.py").read_text(encoding="utf-8")
    for name, following in (("atualizar_usuario", "atualizar_senha_usuario"), ("inativar_usuario", "ativar_usuario")):
        section = models[models.index(f"def {name}("):models.index(f"def {following}(")]
        assert 'SELECT id FROM condominios WHERE id=%s FOR UPDATE' in section
        assert section.index('SELECT id FROM condominios WHERE id=%s FOR UPDATE') < section.index('SELECT COUNT(*) AS total FROM usuarios')
    section = platform[platform.index("def definir_status_usuario_tenant("):platform.index("def criar_condominio_com_usuario(")]
    assert 'SELECT id FROM condominios WHERE id=%s FOR UPDATE' in section


def test_rbac_migration_does_not_commit_before_checksum_record():
    sql = Path("migrations/0020_tenant_rbac_roles.sql").read_text(encoding="utf-8")
    runner = Path("migrations/migrate.py").read_text(encoding="utf-8")
    assert "BEGIN;" not in sql
    assert "COMMIT;" not in sql
    assert "cur.execute(sql)" in runner
    assert "INSERT INTO schema_migrations(version, checksum)" in runner
    assert runner.index("cur.execute(sql)") < runner.index("INSERT INTO schema_migrations(version, checksum)")
    assert runner.index("INSERT INTO schema_migrations(version, checksum)") < runner.index("conn.commit()", runner.index("cur.execute(sql)"))


def test_platform_provisioning_requires_first_tenant_admin():
    platform = Path("database/platform.py").read_text(encoding="utf-8")
    route = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    section = platform[platform.index("def criar_usuario_tenant("):]
    assert 'if nivel not in ("admin_condominio", "administrativo", "porteiro"):' in section
    assert 'if cur.fetchone()["total"] == 0 and nivel != "admin_condominio":' in section
    assert "Cadastre primeiro um administrador do condomínio." in section
    assert "FOR UPDATE" in section
    assert 'flash("Perfil de usuário inválido.", "erro")' in route
