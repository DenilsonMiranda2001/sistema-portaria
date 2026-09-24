from pathlib import Path


ROUTES = Path("routes/hardware_admin.py").read_text(encoding="utf-8")
REPO = Path("hardware/repository.py").read_text(encoding="utf-8")


def test_credential_admin_is_condominium_admin_only():
    start = ROUTES.index('@hardware_admin_bp.get("/credenciais")')
    end = ROUTES.index('@hardware_admin_bp.get("/incidentes")')
    segment = ROUTES[start:end]
    assert segment.count('@roles_required("admin_condominio")') == 3


def test_raw_tag_is_hashed_before_persistence():
    method = REPO.split("def create_resident_credential", 1)[1].split("def deactivate_credential", 1)[0]
    assert "credential_fingerprint(raw_identifier)" in method
    assert "raw_identifier" not in method.split("cur.execute", 1)[1]


def test_resident_credential_creation_is_tenant_scoped_and_active_only():
    method = REPO.split("def create_resident_credential", 1)[1].split("def deactivate_credential", 1)[0]
    assert "m.condominio_id=%s AND m.ativo" in method


def test_audit_does_not_store_raw_identifier():
    segment = ROUTES.split("def criar_credencial_morador", 1)[1].split("def desativar_credencial", 1)[0]
    audit = segment.split("registrar_auditoria_cursor", 1)[1]
    assert "raw_identifier" not in audit
    assert '"tipo": credential_type' in audit
