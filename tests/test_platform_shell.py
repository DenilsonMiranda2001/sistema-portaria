from pathlib import Path


def test_platform_templates_do_not_inherit_tenant_shell():
    for path in ("templates/platform_condominios.html", "templates/platform_condominio_detalhe.html"):
        source = Path(path).read_text(encoding="utf-8")
        assert '{% extends "platform_base.html" %}' in source
        assert '{% extends "base.html" %}' not in source


def test_platform_shell_keeps_csrf_logout_and_no_tenant_navigation():
    source = Path("templates/platform_base.html").read_text(encoding="utf-8")
    assert "global_csrf_token()" in source
    assert "auth.logout" in source
    for endpoint in ("visitantes.cadastro", "moradores.listar", "encomendas.painel", "admin.usuarios"):
        assert endpoint not in source
