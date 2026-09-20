from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def test_all_templates_parse_successfully():
    root = Path("templates")
    env = Environment(loader=FileSystemLoader(str(root)))
    templates = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.html"))
    assert templates
    for template in templates:
        source = env.loader.get_source(env, template)[0]
        env.parse(source)


def test_repository_does_not_track_runtime_or_private_photo_artifacts():
    # CI also checks git ls-files; this contract documents the repository boundary.
    ignored = Path(".gitignore").read_text(encoding="utf-8")
    assert "venv/" in ignored
    assert "__pycache__/" in ignored
    assert "static/fotos/" in ignored


def test_visitor_registration_does_not_create_presence():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    cadastro = route[route.index("def cadastro"):route.index("# LISTAGEM")]
    assert "entrada={" not in cadastro
    assert 'usuario_id=session["usuario_id"]' in cadastro
    assert "visitantes.ativos" not in cadastro


def test_csv_import_preserves_address_and_has_csrf():
    route = Path("routes/visitantes.py").read_text(encoding="utf-8")
    model = Path("database/models.py").read_text(encoding="utf-8")
    template = Path("templates/importar_visitantes.html").read_text(encoding="utf-8")
    assert "formatar_endereco_condominio" in route
    assert "condominio_id, nome, cpf, endereco, tipo" in model
    assert 'name="csrf_token"' in template
