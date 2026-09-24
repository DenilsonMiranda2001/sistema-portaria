from datetime import datetime, time, timezone
from hardware.policy import evaluate_access_policies


AT = datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc)


def test_policy_is_fail_closed_when_none_match():
    decision = evaluate_access_policies([], device_id="gate-a", at=AT)
    assert not decision.allowed
    assert decision.reason == "no_matching_policy"


def test_policy_can_limit_credential_to_one_device():
    policies = [{"id": "p1", "ativo": True, "device_id": "gate-a", "dias_semana": [3]}]
    assert evaluate_access_policies(policies, device_id="gate-a", at=AT).allowed
    assert not evaluate_access_policies(policies, device_id="gate-b", at=AT).allowed


def test_policy_enforces_validity_and_schedule():
    policies = [{
        "id": "p2", "ativo": True, "dias_semana": [3],
        "valido_de": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "valido_ate": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "hora_inicio": time(8, 0), "hora_fim": time(18, 0),
    }]
    assert evaluate_access_policies(policies, device_id="gate-a", at=AT).allowed
    late = datetime(2026, 9, 24, 22, 0, tzinfo=timezone.utc)
    assert not evaluate_access_policies(policies, device_id="gate-a", at=late).allowed


def test_overnight_window_is_supported():
    policies = [{"ativo": True, "dias_semana": [3], "hora_inicio": time(22), "hora_fim": time(6), "timezone": "UTC"}]
    at = datetime(2026, 9, 24, 23, 0, tzinfo=timezone.utc)
    assert evaluate_access_policies(policies, device_id="gate-a", at=at).allowed
