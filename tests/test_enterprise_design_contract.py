from pathlib import Path


def test_product_shell_uses_single_design_system_and_secure_logout():
    html=Path("templates/base.html").read_text(encoding="utf-8")
    css=Path("static/design-system.css").read_text(encoding="utf-8")
    assert "design-system.css" in html
    for legacy in ("style.css","enterprise-v2.css","portaria-control.css","portaria-premium-v3.css"):
        assert legacy not in html
    assert 'class="saas-sidebar"' not in html
    assert 'method="post" action="{{ url_for(\'auth.logout\') }}"' in html
    assert "global_csrf_token()" in html
    assert "@media" in css


def test_product_navigation_remains_role_aware():
    html=Path("templates/base.html").read_text(encoding="utf-8")
    assert 'g.current_user and g.current_user.get("nivel") == "admin_condominio"' in html
    assert 'session.get("usuario_tipo") in ("admin_condominio", "admin")' not in html
    for endpoint in ("main.index","visitantes.cadastro","visitantes.visitantes","moradores.listar","encomendas.painel","admin.usuarios"):
        assert endpoint in html
