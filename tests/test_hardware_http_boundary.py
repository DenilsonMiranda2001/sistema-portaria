from types import SimpleNamespace
from unittest.mock import patch

from hardware.http_boundary import HardwareHttpError
from routes.hardware import hardware_bp


def _client():
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(hardware_bp)
    return app.test_client()


def test_simulator_endpoint_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HARDWARE_SIMULATOR_HTTP_ENABLED", raising=False)
    response = _client().post("/api/hardware/simulator/events", data=b"{}")
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_oversized_body_is_rejected_before_ingest(monkeypatch):
    monkeypatch.setenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "true")
    with patch("routes.hardware.ingest_simulator_request") as ingest:
        response = _client().post(
            "/api/hardware/simulator/events",
            data=b"x" * (32 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.get_json()["error"] == "payload_too_large"
    ingest.assert_not_called()


def test_authentication_failure_is_mapped_without_internal_reason(monkeypatch):
    monkeypatch.setenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "true")
    with patch(
        "routes.hardware.ingest_simulator_request",
        side_effect=HardwareHttpError(401, "hardware_auth_failed"),
    ):
        response = _client().post("/api/hardware/simulator/events", data=b"{}")
    assert response.status_code == 401
    assert response.get_json()["error"] == "hardware_auth_failed"


def test_accepted_event_returns_stable_http_contract(monkeypatch):
    monkeypatch.setenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "true")
    processed = SimpleNamespace(accepted=True, duplicate=False)
    decision = SimpleNamespace(granted=True)
    with patch("routes.hardware.ingest_simulator_request", return_value=(processed, decision)):
        response = _client().post("/api/hardware/simulator/events", data=b"{}")
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["accepted"] is True
    assert payload["duplicate"] is False
    assert payload["granted"] is True


def test_duplicate_event_returns_no_new_decision(monkeypatch):
    monkeypatch.setenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "true")
    processed = SimpleNamespace(accepted=True, duplicate=True)
    with patch("routes.hardware.ingest_simulator_request", return_value=(processed, None)):
        response = _client().post("/api/hardware/simulator/events", data=b"{}")
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["duplicate"] is True
    assert payload["granted"] is None
