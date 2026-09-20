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
