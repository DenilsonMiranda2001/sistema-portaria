from pathlib import Path


def test_access_service_requires_online_device_and_persisted_policy():
    source = Path("hardware/service.py").read_text(encoding="utf-8")
    assert "repo.device_is_online" in source
    assert "repo.list_access_policies" in source
    assert "evaluate_access_policies" in source


def test_access_service_has_no_permissive_authorization_callback():
    source = Path("hardware/service.py").read_text(encoding="utf-8")
    assert "authorization_check=" not in source.split("def __init__", 1)[1].split("def ingest", 1)[0]
    assert "return decision" in source
    assert "PolicyDecision" in Path("hardware/policy.py").read_text(encoding="utf-8")


def test_repository_fingerprint_lookup_remains_tenant_scoped():
    source = Path("hardware/repository.py").read_text(encoding="utf-8")
    assert "def get_credential_by_fingerprint" in source
    assert "WHERE condominio_id=%s AND identificador_hash=%s" in source
