from datetime import datetime, time, timezone
from hardware.policy import evaluate_access_policies


def _policy(**overrides):
    value = {
        "id": "p1", "ativo": True, "device_id": None, "zona": None,
        "valido_de": None, "valido_ate": None, "dias_semana": [0,1,2,3,4,5,6],
        "hora_inicio": time(8, 0), "hora_fim": time(18, 0),
        "timezone": "America/Sao_Paulo",
    }
    value.update(overrides)
    return value


def test_schedule_is_evaluated_in_policy_local_timezone():
    # 13:00 UTC is 10:00 in Sao Paulo/Brasilia standard offset.
    decision = evaluate_access_policies([_policy()], device_id="gate", at=datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc))
    assert decision.allowed


def test_invalid_timezone_fails_closed():
    decision = evaluate_access_policies([_policy(timezone="Invalid/Timezone")], device_id="gate", at=datetime.now(timezone.utc))
    assert not decision.allowed


def test_naive_event_timestamp_is_rejected():
    try:
        evaluate_access_policies([_policy()], device_id="gate", at=datetime(2026, 1, 5, 10, 0))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive datetime must be rejected")


def test_migration_enforces_complete_time_window_and_valid_weekdays():
    source = open("migrations/0022_hardware_integration_foundation.sql", encoding="utf-8").read()
    assert "CHECK ((hora_inicio IS NULL) = (hora_fim IS NULL))" in source
    assert "dias_semana <@ ARRAY[0,1,2,3,4,5,6]::SMALLINT[]" in source
    assert "cardinality(dias_semana) > 0" in source
