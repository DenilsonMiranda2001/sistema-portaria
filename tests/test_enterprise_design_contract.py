from pathlib import Path


def test_enterprise_shell_uses_top_navigation_mobile_and_secure_logout():
    html = Path("templates/base.html").read_text(encoding="utf-8")
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert 'class="enterprise-header"' in html
    assert 'class="enterprise-nav"' in html
    assert 'class="saas-sidebar"' not in html
    assert "topnav-open" in html and "topnav-open" in css
    assert 'method="post" action="{{ url_for(\'auth.logout\') }}"' in html
    assert "global_csrf_token()" in html
    assert "@media(max-width:820px)" in css


def test_enterprise_navigation_remains_role_aware():
    html = Path("templates/base.html").read_text(encoding="utf-8")
    assert 'session.get("usuario_tipo") == "admin"' in html
    for endpoint in ("main.index", "visitantes.cadastro", "visitantes.visitantes", "moradores.listar", "encomendas.painel", "admin.usuarios"):
        assert endpoint in html
