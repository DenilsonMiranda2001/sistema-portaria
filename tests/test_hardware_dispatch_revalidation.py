from pathlib import Path
REPO=Path("hardware/repository.py").read_text(encoding="utf-8")
WORKER=Path("hardware/worker.py").read_text(encoding="utf-8")

def test_grant_access_is_revalidated_before_adapter_io():
    assert "access_command_still_authorized" in WORKER
    check=WORKER.index("access_command_still_authorized")
    send=WORKER.index("adapter.send_command")
    assert check < send
    assert "authorization_revoked" in WORKER

def test_revalidation_requires_active_credential_policy_zone_and_device():
    method=REPO.split("def access_command_still_authorized",1)[1].split("def finish_command",1)[0]
    assert "cred.ativo" in method
    assert "p.ativo" in method
    assert "z.ativo" in method
    assert "d.ativo" in method
    assert "d.auth_revoked_em IS NULL" in method
    assert "cmd.condominio_id=%s" in method

def test_revalidation_is_bound_to_original_granted_event():
    method=REPO.split("def access_command_still_authorized",1)[1].split("def finish_command",1)[0]
    assert "dec.external_event_id=cmd.payload->>'source_event_id'" in method
    assert "dec.granted" in method
    assert "cred.identificador_hash=ev.credential_hash" in method

def test_revalidation_rejects_command_expired_after_claim():
    method=REPO.split("def access_command_still_authorized",1)[1].split("def finish_command",1)[0]
    assert "cmd.expira_em IS NULL OR cmd.expira_em > CURRENT_TIMESTAMP" in method

def test_revalidation_rechecks_policy_validity_weekday_and_time_window():
    method=REPO.split("def access_command_still_authorized",1)[1].split("def finish_command",1)[0]
    assert "p.valido_de IS NULL OR p.valido_de <= CURRENT_TIMESTAMP" in method
    assert "p.valido_ate IS NULL OR p.valido_ate > CURRENT_TIMESTAMP" in method
    assert "EXTRACT(ISODOW FROM CURRENT_TIMESTAMP AT TIME ZONE p.timezone)" in method
    assert "p.hora_inicio <= p.hora_fim" in method
    assert "CURRENT_TIMESTAMP AT TIME ZONE p.timezone" in method

def test_revoked_access_command_is_terminal_not_retried():
    assert 'error="authorization_revoked"' in WORKER
    revoked=WORKER.split('error="authorization_revoked"',1)[1][:180]
    assert "retryable=False" in revoked
    finish=REPO.split("def finish_command",1)[1]
    assert 'failure_status = "failed" if retryable else "expired"' in finish

def test_ambiguous_grant_access_io_failure_is_not_retried():
    assert 'retryable = row["tipo"] != HardwareCommandType.GRANT_ACCESS.value' in WORKER
    assert "the physical device may already have acted" in WORKER

def test_rejected_access_command_requires_explicit_safe_retry_opt_in():
    contracts=Path("hardware/contracts.py").read_text(encoding="utf-8")
    assert "safe_to_retry: bool = False" in contracts
    assert 'getattr(result, "safe_to_retry", False)' in WORKER
    assert "retryable_rejection" in WORKER
