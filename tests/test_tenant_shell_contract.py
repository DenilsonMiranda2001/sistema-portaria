from pathlib import Path


def test_tenant_shell_keeps_security_and_navigation_contracts():
    source = Path("templates/base.html").read_text(encoding="utf-8")
    assert 'method="post"' in source
    assert "global_csrf_token()" in source
    assert "auth.logout" in source
    assert 'meta name="csrf-token"' in source
    for endpoint in ("main.index", "visitantes.cadastro", "visitantes.visitantes", "moradores.listar", "encomendas.painel"):
        assert endpoint in source


def test_shells_are_structurally_separate():
    tenant = Path("templates/base.html").read_text(encoding="utf-8")
    platform = Path("templates/platform_base.html").read_text(encoding="utf-8")
    assert "modalFoto" not in tenant
    assert "modalFoto" not in platform
    assert "{% block global_overlays %}" in tenant
    assert "ADMINISTRAÇÃO DA PLATAFORMA" in platform
