from pathlib import Path

from database.encomendas import TRANSICOES_ENCOMENDA


def test_package_state_machine_has_terminal_states():
    assert TRANSICOES_ENCOMENDA["retirada"] == set()
    assert TRANSICOES_ENCOMENDA["entregue_na_porta"] == set()
    assert TRANSICOES_ENCOMENDA["cancelada"] == set()


def test_package_state_machine_only_moves_legacy_states_into_central_custody():
    for legacy in ("recebida", "aguardando_resposta", "morador_em_casa"):
        assert TRANSICOES_ENCOMENDA[legacy] == {"retida_portaria", "cancelada"}
    assert TRANSICOES_ENCOMENDA["retida_portaria"] == {"retirada", "cancelada"}


def test_new_packages_start_in_central_custody():
    source = Path("database/encomendas.py").read_text(encoding="utf-8")
    assert "'retida_portaria'" in source


def test_operational_package_ui_does_not_offer_door_delivery():
    source = Path("templates/encomendas/_macros.html").read_text(encoding="utf-8")
    assert 'name="status" value="entregue_na_porta"' not in source
    assert 'name="status" value="morador_em_casa"' not in source
    assert "Confirmar retirada" in source
