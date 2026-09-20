from pathlib import Path


def test_critical_operations_use_cursor_level_audit():
    audit = Path("utils/audit.py").read_text(encoding="utf-8")
    packages = Path("database/encomendas.py").read_text(encoding="utf-8")
    models = Path("database/models.py").read_text(encoding="utf-8")
    assert "def registrar_auditoria_cursor" in audit
    for event in ("encomenda.lote_criado", "encomenda.criada", "encomenda.lote_status", "encomenda.status"):
        assert event in packages
    assert '"visita.entrada"' in models
    assert '"visita.saida"' in models


def test_routes_do_not_duplicate_atomic_visit_or_package_audits():
    visitantes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    encomendas = Path("routes/encomendas.py").read_text(encoding="utf-8")
    assert 'registrar_auditoria("visita.entrada"' not in visitantes
    assert 'registrar_auditoria("visita.saida"' not in visitantes
    assert 'registrar_auditoria("encomenda.lote_criado"' not in encomendas
    assert 'registrar_auditoria("encomenda.criada"' not in encomendas
    assert 'registrar_auditoria("encomenda.status"' not in encomendas
