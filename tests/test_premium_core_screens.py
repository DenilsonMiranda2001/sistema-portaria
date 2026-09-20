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
