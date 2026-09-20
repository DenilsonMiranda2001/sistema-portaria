from pathlib import Path


def test_platform_routes_have_no_raw_cursor_sql():
    source = Path("routes/platform_admin.py").read_text(encoding="utf-8")
    assert "cur.execute(" not in source
    assert "conectar()" not in source


def test_visit_workflows_validate_actor_and_resident_unit():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert "Usuário de entrada inválido para este condomínio." in source
    assert "Usuário de saída inválido para este condomínio." in source
    assert "O morador selecionado não pertence à unidade informada." in source


def test_resident_atomic_workflows_reject_inactive_unit_reuse():
    source = Path("database/models.py").read_text(encoding="utf-8")
    assert source.count("Esta unidade existe, mas está inativa.") >= 2
