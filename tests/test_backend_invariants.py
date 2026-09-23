from pathlib import Path


def test_platform_routes_have_no_raw_cursor_sql():
    source = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    assert "cur.execute(" not in source
    assert "conectar()" not in source


def test_visit_workflows_validate_actor_and_resident_unit():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert "Usuário de entrada inválido para este condomínio." in source
    assert "Usuário de saída inválido para este condomínio." in source
    assert "O morador selecionado não pertence à unidade informada." in source


def test_resident_atomic_workflows_reject_inactive_unit_reuse():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert source.count("Esta unidade existe, mas está inativa.") >= 2


def test_visitor_profile_address_is_separate_from_visit_destination():
    models = Path("database/models.py").read_text(encoding="utf-8")
    migration = Path("migrations/0011_visitor_profile_address.sql").read_text(encoding="utf-8")
    routes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS endereco TEXT" in migration
    assert "endereco=None, entrada=None" in models
    assert 'endereco=endereco' in routes
    cadastro = routes[routes.index("def cadastro"):routes.index("# LISTAGEM")]
    assert "entrada={" not in cadastro


def test_central_package_reception_is_default():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert "'retida_portaria'" in source
    assert "retirada" in source


def test_noop_locked_mutations_close_transactions():
    models = Path("database/models.py").read_text(encoding="utf-8")
    platform = Path("database/platform.py").read_text(encoding="utf-8")
    packages = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert 'conn.rollback()\n                return False' in models
    assert platform.count('conn.rollback()\n                    return False') >= 1
    assert 'conn.rollback()\n                return False' in packages


def test_audit_ip_hash_is_safe_without_request_context():
    audit = Path("utils/audit.py").read_text(encoding="utf-8")
    assert "has_request_context" in audit
    assert "if not has_request_context()" in audit


def test_login_identity_invariant_migration_exists():
    migration = Path("migrations/0012_login_identity_invariant.sql").read_text(encoding="utf-8")
    assert "JOIN platform_admins" in migration
    assert "duplicate tenant login" in migration


def test_open_visit_uniqueness_is_enforced_at_database_level():
    migration = Path("migrations/0013_operational_integrity_indexes.sql").read_text(encoding="utf-8")
    verification = Path("migrations/0014_verify_live_access_invariant.sql").read_text(encoding="utf-8")
    assert "uq_visita_aberta_visitante_tenant" in migration
    assert "WHERE data_saida IS NULL" in migration
    assert "HAVING COUNT(*) > 1" in verification
    assert "uq_visita_aberta_visitante_tenant" in verification


def test_hot_operational_queries_have_tenant_scoped_indexes():
    migration = Path("migrations/0013_operational_integrity_indexes.sql").read_text(encoding="utf-8")
    assert "idx_visitas_tenant_abertas" in migration
    assert "idx_encomendas_tenant_custodia" in migration
    assert "idx_moradores_tenant_ativos_unidade" in migration


def test_entry_lock_precedes_active_visit_check():
    source = Path("database/models.py").read_text(encoding="utf-8")
    block = source[source.index("def registrar_entrada"):source.index("def registrar_saida")]
    assert block.index("FOR UPDATE") < block.index("data_saida IS NULL")


def test_applied_migrations_are_forward_only():
    verification = Path("migrations/0014_verify_live_access_invariant.sql").read_text(encoding="utf-8")
    assert "pg_indexes" in verification
    assert "uq_visita_aberta_visitante_tenant" in verification


def test_live_access_dynamic_rendering_avoids_innerhtml_and_keyboard_exit_has_csrf():
    source = Path("templates/ativos.html").read_text(encoding="utf-8")
    script = source[source.index("<script>"):]
    assert ".innerHTML" not in script
    assert "replaceChildren" in script
    assert 'token.name="csrf_token"' in script
    assert "data_entrada" in Path("routes/visitantes.py").read_text(encoding="utf-8")


def test_package_state_machine_cannot_reenter_obsolete_door_delivery_flow():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    block = source[source.index("TRANSICOES_ENCOMENDA"):source.index("def atualizar_status_encomenda")]
    assert '"recebida": {"retida_portaria", "cancelada"}' in block
    assert '"aguardando_resposta": {"retida_portaria", "cancelada"}' in block
    assert '"morador_em_casa": {"retida_portaria", "cancelada"}' in block


def test_daily_dashboard_counters_use_index_friendly_time_ranges():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert "DATE(data_entrada) = CURRENT_DATE" not in source
    assert "DATE(data_saida) = CURRENT_DATE" not in source
    assert "data_entrada >= CURRENT_DATE" in source
    assert "data_saida >= CURRENT_DATE" in source


def test_audit_ip_pseudonymization_uses_keyed_hmac():
    source = Path("utils/audit.py").read_text(encoding="utf-8")
    assert "hmac.new(" in source
    assert 'salt.encode("utf-8")' in source
    assert 'ip.encode("utf-8")' in source


def test_package_dashboard_uses_index_friendly_time_ranges():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert "data_retirada::date = CURRENT_DATE" not in source
    assert "atualizado_em::date = CURRENT_DATE" not in source
    assert "data_retirada >= CURRENT_DATE" in source
    assert "atualizado_em >= CURRENT_DATE" in source


def test_package_dashboard_has_tenant_time_indexes():
    migration = Path("migrations/0018_package_dashboard_indexes.sql").read_text(encoding="utf-8")
    assert "idx_encomendas_tenant_retirada" in migration
    assert "idx_encomendas_tenant_atualizado_final" in migration


def test_package_status_mutations_validate_actor_inside_tenant_transaction():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert source.count('SELECT 1 FROM usuarios WHERE id=%s AND condominio_id=%s AND ativo=TRUE') >= 2
    assert source.count('raise ValueError("Usuário inválido para este condomínio.")') >= 3


def test_user_mutations_validate_admin_actor_inside_tenant_transaction():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert source.count("AND ativo=TRUE AND nivel='admin'") >= 5
    assert source.count('raise ValueError("Administrador inválido para este condomínio.")') >= 5


def test_resident_mutations_validate_actor_inside_tenant_transaction():
    source = Path("database/models.py").read_text(encoding="utf-8")
    resident_section = source[source.index("def cadastrar_morador_com_unidade"):source.index("# ──────────────────────────────────────────────────────────────\n# VISITANTES")]
    assert resident_section.count('raise ValueError("Usuário inválido para este condomínio.")') >= 4


def test_dashboard_routes_require_authenticated_roles():
    source = Path("routes/main.py").read_text(encoding="utf-8")
    assert source.count('@roles_required("admin", "funcionario", "platform_admin")') >= 2


def test_platform_mutations_validate_active_control_plane_actor():
    source = Path("database/platform.py").read_text(encoding="utf-8")
    assert source.count("SELECT 1 FROM platform_admins WHERE id=%s AND ativo=TRUE") >= 5
    assert source.count('raise ValueError("Administrador da plataforma inválido.")') >= 5


def test_database_connections_bound_query_and_idle_transaction_time():
    source = Path("database/connection.py").read_text(encoding="utf-8")
    assert "statement_timeout = '15s'" in source
    assert "idle_in_transaction_session_timeout = '30s'" in source


def test_visitor_profile_mutations_validate_actor_inside_tenant_transaction():
    source = Path("database/models.py").read_text(encoding="utf-8")
    visitor_section = source[source.index("def cpf_ja_cadastrado"):]
    assert visitor_section.count('raise ValueError("Usuário inválido para este condomínio.")') >= 7


def test_visitor_lookup_endpoints_reject_unbounded_or_invalid_searches():
    source = Path("routes/visitantes.py").read_text(encoding="utf-8")
    buscar_ajax = source[source.index("def buscar_ajax"):source.index("def buscar_cpf_ajax")]
    buscar_cpf = source[source.index("def buscar_cpf_ajax"):source.index("def buscar_ativos_ajax")]
    buscar_ativos = source[source.index("def buscar_ativos_ajax"):source.index("def buscar_moradores_ajax_rota")]
    assert "if len(termo) < 2" in buscar_ajax
    assert "if len(cpf) != 11 or not validar_cpf(cpf)" in buscar_cpf
    assert "if len(termo) < 2" in buscar_ativos


def test_resident_activation_routes_do_not_report_false_success():
    source = Path("routes/moradores.py").read_text(encoding="utf-8")
    assert 'alterou = inativar_morador(id, session["usuario_id"])' in source
    assert '"Morador já estava inativo."' in source
    assert 'alterou = ativar_morador(id, session["usuario_id"])' in source
    assert '"Morador já estava ativo."' in source


def test_delivery_people_domain_is_tenant_scoped_and_package_link_is_tenant_safe():
    migration = Path("migrations/0019_delivery_people.sql").read_text(encoding="utf-8")
    repository = Path("database/entregadores.py").read_text(encoding="utf-8")
    packages = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert "CREATE TABLE entregadores" in migration
    assert "FOREIGN KEY (entregador_id, condominio_id)" in migration
    assert "REFERENCES entregadores(id, condominio_id)" in migration
    assert "uq_entregadores_tenant_documento" in migration
    assert repository.count("condominio_id=%s") >= 5
    assert "Usuário inválido para este condomínio." in repository
    assert "Entregador inválido para este condomínio." in packages
    assert "entregador_id, nome_entregador" in packages


def test_delivery_people_routes_enforce_roles_and_admin_only_status():
    source = Path("routes/entregadores.py").read_text(encoding="utf-8")
    assert source.count('@roles_required("admin", "funcionario")') >= 3
    status = source[source.index('def status(entregador_id)') - 120:]
    assert '@roles_required("admin")' in status


def test_platform_queries_expose_tenant_health_metrics():
    source = Path("database/platform.py").read_text(encoding="utf-8")
    for metric in ("acessos_abertos", "encomendas_pendentes", "ultima_atividade", "admins_ativos"):
        assert metric in source
    assert "moradores_ativos" in source
    assert "visitantes_cadastrados" in source


def test_platform_control_plane_has_real_operational_overview():
    source = Path("database/platform.py").read_text(encoding="utf-8")
    route = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    template = Path("templates/platform_condominios.html").read_text(encoding="utf-8")
    assert "def resumo_operacional_plataforma" in source
    assert "eventos_24h" in source
    assert "actor_tipo='platform_admin'" in source
    assert "resumo_operacional_plataforma()" in route
    assert "platform-audit-feed" in template
    assert "encomendas_pendentes" in template


def test_migrations_use_dedicated_nonpooled_connection():
    connection = Path("database/connection.py").read_text(encoding="utf-8")
    migrate = Path("migrations/migrate.py").read_text(encoding="utf-8")
    assert "def conectar_dedicado(" in connection
    assert 'conectar_dedicado("sistema-portaria-migrations")' in migrate
    assert "liberar(conn)" not in migrate
    assert "conn.close()" in migrate


def test_authenticated_tenant_identity_includes_condominium_name_for_header():
    models = Path("database/models.py").read_text(encoding="utf-8")
    base = Path("templates/base.html").read_text(encoding="utf-8")
    identity = models[models.index("def buscar_usuario_por_id"):models.index("def buscar_usuario(")]
    assert identity.count("c.nome AS condominio_nome") == 2
    assert 'g.current_user.get("condominio_nome", "Condomínio")' in base
    assert '"Porteiro" if session.get("usuario_tipo") == "funcionario"' in base


def test_visitor_forms_share_layout_and_destination_semantics():
    registration = Path("templates/cadastro.html").read_text(encoding="utf-8")
    editing = Path("templates/editar.html").read_text(encoding="utf-8")
    for template in (registration, editing):
        assert 'class="pc-form-shell"' in template
        assert 'class="pc-form-main"' in template
        assert 'class="pc-field pc-span-2"' in template
        assert "Destino no condomínio" in template
        assert "Endereço do visitante" not in template
        assert 'class="camera-box" style="display:none"' in template
        assert 'class="preview-box" style="display:none"' in template
    assert 'class="pc-form-grid pc-form-grid-3"' in editing
