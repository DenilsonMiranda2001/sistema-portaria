from pathlib import Path

SOURCE = Path("routes/hardware_admin.py").read_text(encoding="utf-8")


def test_device_zone_assignment_validates_uuid_before_database():
    method = SOURCE.split("def vincular_zona_dispositivo", 1)[1].split("def criar_simulador", 1)[0]
    assert "uuid.UUID(zone_id)" in method
    assert 'flash("Ponto de acesso inválido."' in method


def test_duplicate_credential_is_a_friendly_validation_error():
    method = SOURCE.split("def criar_credencial_morador", 1)[1].split("def desativar_credencial", 1)[0]
    assert "except errors.UniqueViolation:" in method
    assert "Esta credencial já está cadastrada neste condomínio." in method
    assert "conn.rollback()" in method


def test_one_time_device_secret_responses_are_not_cacheable():
    provision = SOURCE.split("def criar_simulador", 1)[1].split("def rotacionar", 1)[0]
    rotation = SOURCE.split("def rotacionar", 1)[1].split("def revogar", 1)[0]
    for method in (provision, rotation):
        assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in method
        assert 'response.headers["Pragma"] = "no-cache"' in method


def test_duplicate_access_policy_is_a_friendly_validation_error():
    method = SOURCE.split("def criar_permissao", 1)[1].split("def desativar_permissao", 1)[0]
    assert "except errors.UniqueViolation:" in method
    assert "Esta permissão de acesso já está cadastrada." in method
    assert "conn.rollback()" in method
