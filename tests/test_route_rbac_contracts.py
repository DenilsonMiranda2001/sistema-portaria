from pathlib import Path


def _assert_route_decorated(source, route_fragment, roles_fragment):
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if route_fragment in line and "_bp.route(" in line:
            nearby = "\n".join(lines[i:i+4])
            assert roles_fragment in nearby, nearby
            return
    raise AssertionError(f"route not found: {route_fragment}")


def test_sensitive_tenant_routes_have_explicit_rbac():
    moradores = Path("routes/moradores.py").read_text(encoding="utf-8")
    visitantes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    encomendas = Path("routes/encomendas.py").read_text(encoding="utf-8")
    _assert_route_decorated(moradores, '/<int:id>/inativar', '@roles_required("admin")')
    _assert_route_decorated(moradores, '/<int:id>/ativar', '@roles_required("admin")')
    _assert_route_decorated(visitantes, '/remover/<int:id>', '@roles_required("admin")')
    _assert_route_decorated(visitantes, '/importar_visitantes', '@roles_required("admin")')
    assert encomendas.count('@roles_required("admin", "funcionario")') >= 7


def test_operational_routes_are_not_left_implicit():
    for path in ("routes/moradores.py", "routes/visitantes.py", "routes/encomendas.py"):
        source = Path(path).read_text(encoding="utf-8")
        route_count = source.count("_bp.route(")
        role_count = source.count("@roles_required(")
        assert route_count == role_count, (path, route_count, role_count)
