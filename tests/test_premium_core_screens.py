from pathlib import Path


def test_core_workspaces_use_enterprise_visual_language_without_weakening_forms():
    active = Path("templates/ativos.html").read_text(encoding="utf-8")
    resident = Path("templates/moradores/form.html").read_text(encoding="utf-8")
    login = Path("templates/login.html").read_text(encoding="utf-8")
    assert "No condomínio" in active and "MONITORAMENTO AO VIVO" in active and "presence-grid" in active
    assert 'name="csrf_token"' in active and "visitantes.saida" in active
    assert "resident-quick-form" in resident and "resident-access-grid" in resident and 'name="csrf_token"' in resident
    assert "moradores.listar" in resident
    assert "Entre na operação" in login and 'autocomplete="current-password"' in login
    assert 'name="csrf_token"' in login


def test_package_templates_use_global_csrf_contract():
    novo = Path("templates/encomendas/novo_lote.html").read_text(encoding="utf-8")
    detalhe = Path("templates/encomendas/lote_detalhe.html").read_text(encoding="utf-8")
    macros = Path("templates/encomendas/_macros.html").read_text(encoding="utf-8")
    combined = novo + detalhe + macros
    assert "csrf_encomendas" not in combined
    assert 'name="csrf_token"' in novo
    assert 'name="csrf_token"' in detalhe
    assert 'name="csrf_token"' in macros
