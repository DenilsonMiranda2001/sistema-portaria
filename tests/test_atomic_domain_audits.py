from pathlib import Path


def test_tenant_user_and_resident_audits_are_not_split_in_routes():
    admin = Path("routes/admin.py").read_text(encoding="utf-8")
    moradores = Path("routes/moradores.py").read_text(encoding="utf-8")
    for event in ("usuario.criado", "usuario.atualizado", "usuario.inativado", "usuario.ativado", "usuario.senha_alterada"):
        assert f'registrar_auditoria("{event}"' not in admin
    for event in ("morador.criado", "morador.atualizado", "morador.inativado", "morador.ativado"):
        assert f'registrar_auditoria("{event}"' not in moradores


def test_visitor_mutation_audits_live_in_transaction_layer():
    models = Path("database/models.py").read_text(encoding="utf-8")
    visitantes = Path("routes/visitantes.py").read_text(encoding="utf-8")
    for event in ("visitante.criado_com_entrada", "visitante.atualizado", "visitante.removido", "visitante.foto_atualizada", "visitante.importacao"):
        assert event in models
    assert 'registrar_auditoria("visitante.criado_com_entrada"' not in visitantes
    assert 'registrar_auditoria("visitante.atualizado"' not in visitantes
