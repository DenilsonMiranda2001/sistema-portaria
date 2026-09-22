from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def test_all_templates_parse_successfully():
    root = Path("templates")
    env = Environment(loader=FileSystemLoader(str(root)))
    templates = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.html"))
    assert templates
    for template in templates:
        source = env.loader.get_source(env, template)[0]
        env.parse(source)


def test_repository_does_not_track_runtime_or_private_photo_artifacts():
    # CI also checks git ls-files; this contract documents the repository boundary.
    ignored = Path(".gitignore").read_text(encoding="utf-8")
    assert "venv/" in ignored
    assert "__pycache__/" in ignored
    assert "static/fotos/" in ignored


def test_visitor_registration_does_not_create_presence():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    cadastro = route[route.index("def cadastro"):route.index("# LISTAGEM")]
    assert "entrada={" not in cadastro
    assert 'usuario_id=session["usuario_id"]' in cadastro
    assert "visitantes.ativos" not in cadastro


def test_csv_import_preserves_address_and_has_csrf():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    model = Path("database/models.py").read_text(encoding="utf-8")
    template = Path("templates/importar_visitantes.html").read_text(encoding="utf-8")
    assert "formatar_endereco_condominio" in route
    assert "condominio_id, nome, cpf, endereco, tipo" in model
    assert 'name="csrf_token"' in template


def test_ajax_mutations_carry_csrf_tokens():
    home = Path("templates/index.html").read_text(encoding="utf-8")
    active = Path("templates/ativos.html").read_text(encoding="utf-8")
    assert 'body.append("csrf_token"' in home
    assert 'token.name="csrf_token"' in active
    visitors = Path("templates/visitantes.html").read_text(encoding="utf-8")
    assert 'name="csrf_token"' in visitors


def test_visitor_photos_use_authorized_route_not_public_static_paths():
    for name in ("ativos.html", "visitantes.html", "editar.html", "historico.html"):
        source = Path("templates", name).read_text(encoding="utf-8")
        assert "static/fotos/" not in source
        assert "visitantes.foto" in source
    routes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    assert '@visitantes_bp.route("/foto/<int:id>")' in routes
    assert "presigned_image_url" in routes


def test_tenant_admin_has_queryable_audit_trail():
    routes = Path("routes/admin.py").read_text(encoding="utf-8")
    model = Path("database/models.py").read_text(encoding="utf-8")
    assert '@admin_bp.route("/auditoria")' in routes
    assert '@roles_required("admin")' in routes[routes.index('@admin_bp.route("/auditoria")'):]
    assert "WHERE a.condominio_id=%s" in model


def test_login_limiter_has_continuous_retention_and_fails_closed():
    auth = Path("routes/auth.py").read_text(encoding="utf-8")
    assert "DELETE FROM login_attempts" in auth
    assert "return True" in auth[auth.index("def _login_rate_limited"):auth.index("def _record_failed_login")]


def test_admin_mutation_forms_keep_csrf_and_post_semantics():
    users = Path("templates/usuarios.html").read_text(encoding="utf-8")
    edit = Path("templates/editar_usuario.html").read_text(encoding="utf-8")
    password = Path("templates/alterar_senha_usuario.html").read_text(encoding="utf-8")
    assert 'action="{{ url_for(\'admin.inativar_usuario_rota\'' in users
    assert 'action="{{ url_for(\'admin.ativar_usuario_rota\'' in users
    assert users.count('name="csrf_token"') >= 3
    assert 'name="csrf_token"' in edit
    assert 'name="csrf_token"' in password


def test_production_webcam_update_uses_private_object_storage():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    block = route[route.index("def atualizar_foto_ajax"):route.index("# IMPORTAÇÃO CSV")]
    assert "save_webcam_image(foto_base64, g.tenant_id)" in block
    assert "temporariamente indisponível" not in block


def test_production_config_validates_private_storage_and_audit_salt():
    config = Path("config.py").read_text(encoding="utf-8")
    for name in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "AUDIT_IP_SALT"):
        assert name in config


def test_private_storage_validates_decoded_image_content():
    source = Path("utils/storage.py").read_text(encoding="utf-8")
    assert "Image.open(stream)" in source
    assert "image.verify()" in source
    assert "FORMAT_EXTENSIONS" in source
    assert "_require_tenant(tenant_id)" in source
    assert 'file_storage.mimetype or "application/octet-stream"' not in source


def test_private_photo_lifecycle_cleans_replaced_and_orphaned_objects():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    storage = Path("utils/storage.py").read_text(encoding="utf-8")
    assert "def delete_image(object_key):" in storage
    assert "visitante = buscar_visitante_por_id(visitante_id)" in route
    assert "delete_image(nome_arquivo)" in route
    assert "delete_image(foto_anterior)" in route
    assert '"foto_url": url_for("visitantes.foto", id=visitante_id)' in route


def test_platform_admin_bootstrap_requires_explicit_production_rotation():
    source = Path("scripts/bootstrap_admin.py").read_text(encoding="utf-8")
    assert "--confirm-production" in source
    assert "--reset-existing" in source
    assert "ON CONFLICT (usuario) DO NOTHING" in source
    assert "Production bootstrap requires --confirm-production." in source


def test_image_validation_has_dimension_and_decompression_bomb_limits():
    source = Path("utils/storage.py").read_text(encoding="utf-8")
    assert "MAX_IMAGE_PIXELS = 20_000_000" in source
    assert "MAX_IMAGE_SIDE = 8_000" in source
    assert "_validate_dimensions(image)" in source
    assert "Image.DecompressionBombError" in source


def test_login_rate_limit_covers_username_and_ip_spraying():
    source = Path("routes/auth.py").read_text(encoding="utf-8")
    assert "LOGIN_LIMIT = 10" in source
    assert "LOGIN_IP_LIMIT = 30" in source
    assert "def _login_ip_key():" in source
    assert "WHERE chave IN (%s, %s)" in source
    assert "cur.execute(statement, (_login_ip_key(), LOGIN_IP_LIMIT))" in source


def test_unknown_login_still_runs_password_hash_verification():
    source = Path("routes/auth.py").read_text(encoding="utf-8")
    assert "DUMMY_PASSWORD_HASH" in source
    assert "check_password_hash(DUMMY_PASSWORD_HASH, senha)" in source
    assert "secrets.token_urlsafe(32)" in source
