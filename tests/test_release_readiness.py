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
    assert '@roles_required("admin_condominio")' in routes[routes.index('@admin_bp.route("/auditoria")'):]
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


def test_dynamic_visitor_search_does_not_interpolate_backend_data_into_html():
    source = Path("templates/visitantes.html").read_text(encoding="utf-8")
    assert "lista.innerHTML +=" not in source
    assert "${v.nome" not in source
    assert "${v.observacao" not in source
    assert "name.textContent" in source
    assert "valueEl.textContent" in source


def test_visit_autocomplete_does_not_render_suggestions_with_inner_html():
    for template in ("templates/cadastro.html", "templates/editar.html"):
        source = Path(template).read_text(encoding="utf-8")
        assert "div.innerHTML = destacar" not in source
        assert "strong.textContent" in source
        assert "document.createTextNode" in source


def test_private_storage_client_requires_complete_credentials():
    source = Path("utils/storage.py").read_text(encoding="utf-8")
    assert "access_key = os.getenv(\"S3_ACCESS_KEY_ID\")" in source
    assert "secret_key = os.getenv(\"S3_SECRET_ACCESS_KEY\")" in source
    assert "if not endpoint or not bucket or not access_key or not secret_key" in source
    assert source.count("client, bucket = _client()") >= 4


def test_visitor_delete_route_logs_unexpected_failures():
    source = Path("routes/visitantes.py").read_text(encoding="utf-8")
    section = source[source.index("def remover(id)"):source.index("def historico(id)")]
    assert 'logger.exception("Erro ao remover visitante")' in section
    assert 'flash("Não foi possível remover o visitante.", "erro")' in section


def test_request_timing_handles_csrf_rejection_before_before_request():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'started_at = getattr(g, "request_started_at", None)' in source
    assert 'if started_at is not None else None' in source
    assert 'duration_ms if duration_ms is not None else 0.0' in source


def test_delivery_people_ui_is_csrf_protected_and_package_intake_supports_linking():
    listing = Path("templates/entregadores/lista.html").read_text(encoding="utf-8")
    form = Path("templates/entregadores/form.html").read_text(encoding="utf-8")
    intake = Path("templates/encomendas/novo_lote.html").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'name="csrf_token"' in listing
    assert 'name="csrf_token"' in form
    assert 'name="entregador_id"' in intake
    assert "entregadores_bp" in app


def test_delivery_people_live_inside_packages_navigation_and_intake_flow():
    base = Path("templates/base.html").read_text(encoding="utf-8")
    macros = Path("templates/encomendas/_macros.html").read_text(encoding="utf-8")
    intake = Path("templates/encomendas/novo_lote.html").read_text(encoding="utf-8")
    routes = Path("routes/entregadores.py").read_text(encoding="utf-8")
    assert '>Entregadores</a>' not in base
    assert "request.endpoint.startswith('entregadores')" in base
    assert "subnav('entregadores')" not in macros
    assert "url_for('entregadores.listar')" in macros
    assert "Cadastrar novo entregador" in intake
    assert "Nome avulso / legado" not in intake
    assert 'next="novo_lote"' not in intake
    assert "next='novo_lote'" in intake
    assert 'destino == "novo_lote"' in routes


def test_server_rendered_active_exit_form_includes_csrf_token():
    ativos = Path("templates/ativos.html").read_text(encoding="utf-8")
    marker = 'action="{{ url_for(\'visitantes.saida\', id=v.id) }}"'
    start = ativos.index(marker)
    form_end = ativos.index("</form>", start)
    form = ativos[start:form_end]
    assert 'name="csrf_token"' in form
    assert "global_csrf_token()" in form


def test_product_ui_avoids_browser_native_confirmation_and_datalist():
    templates = Path("templates")
    sources = "\n".join(path.read_text(encoding="utf-8") for path in templates.rglob("*.html"))
    assert "return confirm(" not in sources
    assert "<datalist" not in sources
    assert "data-pc-confirm" in sources
    assert "pcGlobalConfirm" in Path("templates/base.html").read_text(encoding="utf-8")
    assert "pc-autocomplete-panel" in Path("static/design-system.css").read_text(encoding="utf-8")


def test_home_is_single_screen_and_readability_scale_is_shared():
    home = Path("templates/index.html").read_text(encoding="utf-8")
    css = Path("static/design-system.css").read_text(encoding="utf-8")
    assert "pc-home-summary" in home
    assert "MOVIMENTO RECENTE" not in home
    assert "Portaria mais segura" not in home
    assert "font-size:14px" in css
    assert "height:calc(100vh - 72px)" in css


def test_operational_list_scale_matches_readability_standard():
    css = Path("static/design-system.css").read_text(encoding="utf-8")
    assert ".pc-directory-row,.pc-access-row" in css
    assert "min-height:68px" in css
    assert ".pc-access-photo{width:42px;height:42px" in css
    assert ".pc-access-identity strong{font-size:12px}" in css
    assert ".pc-table td{padding:13px 14px;font-size:12px}" in css


def test_packages_module_uses_current_operational_scale():
    css = Path("static/design-system.css").read_text(encoding="utf-8")
    assert ".pc-packages .pc-package-row" in css
    assert "min-height:82px" in css
    assert ".pc-packages .pc-package-filters input,.pc-packages .pc-package-filters select{min-height:44px" in css
    assert ".pc-packages .pc-lot-head strong{font-size:14px}" in css
    assert ".pc-packages .pc-history-row{min-height:68px" in css
