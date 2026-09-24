from hardware.access import AccessDecisionService, credential_fingerprint
from hardware.simulator import SimulatorAdapter
from hardware.policy import PolicyDecision


def _event(tenant=10, credential="TAG-001"):
    return SimulatorAdapter().normalize_event(
        tenant, "gate-main", {"event_id": "evt-1", "credential": credential}
    )


def test_known_authorized_tag_generates_vendor_neutral_grant_command():
    fp = credential_fingerprint("TAG-001")
    service = AccessDecisionService(
        credential_lookup=lambda tenant, fingerprint: {
            "condominio_id": tenant, "ativo": True, "identificador_hash": fingerprint
        } if fingerprint == fp else None,
        authorization_check=lambda tenant, credential, device: PolicyDecision(True, "test_allowed", "policy-test"),
        command_id_factory=lambda: "cmd-1",
    )
    decision = service.decide(_event())
    assert decision.granted
    assert decision.command.command_id == "cmd-1"
    assert decision.policy_id == "policy-test"
    assert decision.command.payload == {"source_event_id": "evt-1"}
    assert "TAG-001" not in str(decision.command.payload)


def test_unknown_or_unauthorized_tag_never_generates_open_command():
    service = AccessDecisionService(
        credential_lookup=lambda tenant, fingerprint: None,
        authorization_check=lambda tenant, credential, device: PolicyDecision(True, "test_allowed", "policy-test"),
        command_id_factory=lambda: "must-not-run",
    )
    decision = service.decide(_event())
    assert not decision.granted
    assert decision.command is None
    assert decision.reason == "credential_unknown_or_inactive"


def test_cross_tenant_credential_is_rejected():
    service = AccessDecisionService(
        credential_lookup=lambda tenant, fingerprint: {"condominio_id": tenant + 1, "ativo": True},
        authorization_check=lambda tenant, credential, device: PolicyDecision(True, "test_allowed", "policy-test"),
        command_id_factory=lambda: "must-not-run",
    )
    decision = service.decide(_event(tenant=20))
    assert not decision.granted
    assert decision.reason == "tenant_mismatch"
    assert decision.command is None
