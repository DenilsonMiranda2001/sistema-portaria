from pathlib import Path


def test_title_blocks_do_not_swallow_styles_or_content():
    for name in ("cadastro.html","visitantes.html"):
        source=Path("templates",name).read_text(encoding="utf-8")
        title=source.split("{% block title %}",1)[1].split("{% endblock %}",1)[0]
        assert "<style" not in title and "{% block content %}" not in title


def test_registration_uses_shared_responsive_form_system():
    source=Path("templates/cadastro.html").read_text(encoding="utf-8")
    css=Path("static/design-system.css").read_text(encoding="utf-8")
    assert "pc-form-shell" in source and "pc-form-grid" in source
    assert ".pc-form-shell" in css and ".pc-form-grid" in css and "@media" in css


def test_core_operator_screens_use_shared_product_shell():
    base=Path("templates/base.html").read_text(encoding="utf-8")
    visitors=Path("templates/visitantes.html").read_text(encoding="utf-8")
    residents=Path("templates/moradores/lista.html").read_text(encoding="utf-8")
    assert ">Início</a>" in base
    assert "pc-list-toolbar" in visitors and "pc-list-toolbar" in residents


def test_visitor_edit_uses_current_workspace():
    source=Path("templates/editar.html").read_text(encoding="utf-8")
    assert "pc-form-shell" in source and "pc-form-grid" in source and "Salvar alterações" in source


def test_resident_screens_use_current_operational_standard():
    listing=Path("templates/moradores/lista.html").read_text(encoding="utf-8")
    form=Path("templates/moradores/form.html").read_text(encoding="utf-8")
    assert "pc-list-toolbar" in listing and "pc-form-shell" in form and "pc-form-grid" in form
    assert 'name="csrf_token"' in form
    assert "➕" not in listing and "✏️" not in listing and "👁" not in listing
