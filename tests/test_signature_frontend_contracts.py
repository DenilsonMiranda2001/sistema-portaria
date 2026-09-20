from pathlib import Path


def test_signature_dashboard_preserves_operational_contracts():
    source = Path("templates/index.html").read_text(encoding="utf-8")
    assert "command-hero" in source and "command-grid" in source
    for element_id in ("busca", "mensagem", "lista", "ativos", "entradas", "saidas", "moradores", "cadastrados", "ultima_nome", "ultima_hora"):
        assert f'id="{element_id}"' in source
    assert "const input = document.getElementById(\"busca\")" in source


def test_visitor_registration_keeps_secure_form_and_camera_contracts():
    source = Path("templates/cadastro.html").read_text(encoding="utf-8")
    assert "access-form-shell" in source
    assert 'name="csrf_token"' in source
    for element_id in ("btnAbrirCamera", "btnCapturar", "btnFecharCamera", "foto_webcam"):
        assert f'id="{element_id}"' in source
