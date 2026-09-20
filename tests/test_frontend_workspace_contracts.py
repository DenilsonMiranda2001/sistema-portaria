from pathlib import Path


def test_user_admin_uses_shared_tenant_shell():
    source = Path("templates/usuarios.html").read_text(encoding="utf-8")
    assert "{% extends 'base.html' %}" in source
    assert "<html" not in source.lower()
    assert "auth.logout" not in source
    assert "Usuários e acessos" in source


def test_visitor_directory_has_valid_selection_binding():
    source = Path("templates/visitantes.html").read_text(encoding="utf-8")
    assert "selecionarVisitante({ loopindex0 })" not in source
    assert "selecionarVisitante({{ loop.index0 }})" in source
    assert "Novo visitante" in source
