from pathlib import Path


def test_title_blocks_do_not_swallow_styles_or_content():
    for name in ("cadastro.html", "visitantes.html"):
        source = Path("templates", name).read_text(encoding="utf-8")
        title_block = source.split("{% block title %}", 1)[1].split("{% endblock %}", 1)[0]
        assert "<style" not in title_block
        assert "{% block content %}" not in title_block


def test_registration_layout_has_single_responsive_form_system():
    source = Path("templates/cadastro.html").read_text(encoding="utf-8")
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert "access-form-shell" in source
    assert ".form-cadastro-visitante{display:grid" in css
    assert "grid-template-columns:1fr 1fr" in css
    assert "@media(max-width:760px)" in css


def test_front_desk_density_stays_compact():
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert "font-size:clamp(24px,2vw,30px)!important" in css
    assert "min-height:40px!important" in css
    assert "padding:18px 20px!important" in css


def test_desktop_registration_uses_full_viewport_pattern():
    css = Path("static/style.css").read_text(encoding="utf-8")
    resident = Path("templates/moradores/form.html").read_text(encoding="utf-8")
    assert ".quick-access-form{height:calc(100vh - 194px)" in css
    assert "max-width:none!important" in css
    assert "compact-crud-form" in resident


def test_registration_uses_professional_readable_control_sizes():
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert "height:40px!important" in css
    assert "font-size:14px!important" in css
    assert "font-size:13px!important;letter-spacing:.045em!important" in css
    assert "height:38px!important" in css


def test_core_operator_screens_avoid_redundant_page_heroes():
    base = Path("templates/base.html").read_text(encoding="utf-8")
    home = Path("templates/index.html").read_text(encoding="utf-8")
    cadastro = Path("templates/cadastro.html").read_text(encoding="utf-8")
    visitors = Path("templates/visitantes.html").read_text(encoding="utf-8")
    residents = Path("templates/moradores/lista.html").read_text(encoding="utf-8")
    assert ">Início</a>" in base
    assert "command-hero" not in home
    assert "compact-access-head" not in cadastro
    assert "compact-list-toolbar" in visitors
    assert "compact-list-toolbar" in residents


def test_visitor_edit_uses_current_compact_workspace():
    source = Path("templates/editar.html").read_text(encoding="utf-8")
    assert "quick-access-form quick-edit-form" in source
    assert "quick-access-grid" in source
    assert "Salvar alterações" in source
    assert "📝 Editar Visitante" not in source


def test_resident_screens_use_current_operational_standard():
    listing = Path("templates/moradores/lista.html").read_text(encoding="utf-8")
    form = Path("templates/moradores/form.html").read_text(encoding="utf-8")
    assert "compact-list-toolbar" in listing
    assert "csrf_token()" in listing
    assert "resident-quick-form" in form
    assert "quick-access-grid resident-access-grid" in form
    assert "➕" not in listing and "✏️" not in listing and "👁" not in listing
