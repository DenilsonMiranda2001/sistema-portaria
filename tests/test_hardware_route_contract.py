from pathlib import Path


def test_simulator_route_is_feature_flagged_and_size_limited():
    source = Path("routes/hardware.py").read_text(encoding="utf-8")
    assert "HARDWARE_SIMULATOR_HTTP_ENABLED" in source
    assert "MAX_HARDWARE_BODY_BYTES = 32 * 1024" in source
    assert "payload_too_large" in source


def test_hardware_blueprint_uses_machine_auth_not_browser_session():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "csrf.exempt(hardware_bp)" in app
    assert 'endpoint.startswith("hardware.")' in app
    route = Path("routes/hardware.py").read_text(encoding="utf-8")
    assert "ingest_simulator_request" in route


def test_route_does_not_expose_internal_auth_failure_reason():
    boundary = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    assert 'HardwareHttpError(401, "hardware_auth_failed")' in boundary
