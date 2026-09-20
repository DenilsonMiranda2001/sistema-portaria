from database.encomendas import TRANSICOES_ENCOMENDA


def test_package_state_machine_has_terminal_states():
    assert TRANSICOES_ENCOMENDA["retirada"] == set()
    assert TRANSICOES_ENCOMENDA["entregue_na_porta"] == set()
    assert TRANSICOES_ENCOMENDA["cancelada"] == set()


def test_package_state_machine_requires_ordered_operational_flow():
    assert "morador_em_casa" in TRANSICOES_ENCOMENDA["aguardando_resposta"]
    assert "retida_portaria" in TRANSICOES_ENCOMENDA["aguardando_resposta"]
    assert "retirada" not in TRANSICOES_ENCOMENDA["aguardando_resposta"]
    assert "retirada" in TRANSICOES_ENCOMENDA["retida_portaria"]
    assert "entregue_na_porta" in TRANSICOES_ENCOMENDA["morador_em_casa"]
