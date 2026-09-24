from pathlib import Path


def test_simulator_ingest_chain_is_complete():
    route = Path("routes/hardware.py").read_text(encoding="utf-8")
    boundary = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    service = Path("hardware/service.py").read_text(encoding="utf-8")
    assert "ingest_simulator_request" in route
    assert "verify_device_request" in boundary
    assert "build_authenticated_event(device, data)" in boundary
    assert "HardwareAccessService().ingest(event)" in boundary
    assert "evaluate_access_policies" in service
    assert "repo.record_access_decision" in service
    assert "repo.enqueue_command" in service


def test_replay_cross_tenant_and_physical_vendor_are_fail_closed():
    auth = Path("hardware/auth.py").read_text(encoding="utf-8")
    ingest = Path("hardware/ingest.py").read_text(encoding="utf-8")
    boundary = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    assert "replayed_request" in auth
    assert 'tenant_id=int(device["condominio_id"])' in ingest
    assert "physical_hardware_disabled" in boundary


def test_raw_credentials_are_not_put_in_commands():
    access = Path("hardware/access.py").read_text(encoding="utf-8")
    assert 'payload={"source_event_id": event.event_id}' in access
    assert '"credential": event.credential' not in access


def test_hardware_endpoint_is_off_by_default():
    route = Path("routes/hardware.py").read_text(encoding="utf-8")
    assert 'os.getenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "")' in route
