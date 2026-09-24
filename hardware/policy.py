from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Iterable, Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    policy_id: Optional[str] = None


def _time_in_window(now: time, start: Optional[time], end: Optional[time]) -> bool:
    if start is None and end is None:
        return True
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def evaluate_access_policies(
    policies: Iterable[Mapping],
    *,
    device_id: str,
    zone: Optional[str] = None,
    at: Optional[datetime] = None,
) -> PolicyDecision:
    """Fail closed: at least one active matching policy must explicitly allow access."""
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("policy evaluation requires timezone-aware datetime")
    for policy in policies:
        if not policy.get("ativo"):
            continue
        policy_device = policy.get("device_id")
        policy_zone = policy.get("zona")
        if policy_device and str(policy_device) != str(device_id):
            continue
        if policy_zone and policy_zone != zone:
            continue
        valid_from = policy.get("valido_de")
        valid_until = policy.get("valido_ate")
        if valid_from and at < valid_from:
            continue
        if valid_until and at >= valid_until:
            continue
        try:
            local_at = at.astimezone(ZoneInfo(policy.get("timezone") or "America/Sao_Paulo"))
        except ZoneInfoNotFoundError:
            continue
        weekdays = policy.get("dias_semana")
        if weekdays is not None and local_at.weekday() not in weekdays:
            continue
        if not _time_in_window(local_at.timetz().replace(tzinfo=None), policy.get("hora_inicio"), policy.get("hora_fim")):
            continue
        return PolicyDecision(True, "policy_allowed", str(policy.get("id")) if policy.get("id") else None)
    return PolicyDecision(False, "no_matching_policy")
