from types import SimpleNamespace
from unittest.mock import patch

from hardware.http_boundary import HardwareHttpError, ingest_simulator_request
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



def _auth_headers():
    return {
        "X-Hardware-Key-Id": "sim-key",
        "X-Hardware-Timestamp": "2026-09-24T10:00:00+00:00",
        "X-Hardware-Nonce": "0123456789abcdef",
        "X-Hardware-Signature": "signed",
    }


def test_auth_failure_rolls_back_and_always_releases_connection():
    conn = SimpleNamespace(rollback=__import__("unittest").mock.Mock(), commit=__import__("unittest").mock.Mock())
    repo = SimpleNamespace(get_device_auth_identity=__import__("unittest").mock.Mock(), consume_auth_nonce=__import__("unittest").mock.Mock())
    with patch("hardware.http_boundary.conectar", return_value=conn), \
         patch("hardware.http_boundary.liberar") as release, \
         patch("hardware.http_boundary.HardwareRepository", return_value=repo), \
         patch("hardware.http_boundary.verify_device_request", return_value=SimpleNamespace(authenticated=False, device=None)):
        try:
            ingest_simulator_request(headers=_auth_headers(), body=b"{}", presented_secret="secret")
            assert False, "expected HardwareHttpError"
        except HardwareHttpError as exc:
            assert exc.status == 401
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    release.assert_called_once_with(conn)


def test_successful_auth_commits_nonce_before_connection_release():
    calls = []
    conn = SimpleNamespace(
        rollback=__import__("unittest").mock.Mock(side_effect=lambda: calls.append("rollback")),
        commit=__import__("unittest").mock.Mock(side_effect=lambda: calls.append("commit")),
    )
    device = {"id": "device-1", "condominio_id": 7, "vendor": "simulator"}
    repo = SimpleNamespace(get_device_auth_identity=__import__("unittest").mock.Mock(), consume_auth_nonce=__import__("unittest").mock.Mock())
    with patch("hardware.http_boundary.conectar", return_value=conn), \
         patch("hardware.http_boundary.liberar", side_effect=lambda value: calls.append("release")), \
         patch("hardware.http_boundary.HardwareRepository", return_value=repo), \
         patch("hardware.http_boundary.verify_device_request", return_value=SimpleNamespace(authenticated=True, device=device)), \
         patch("hardware.http_boundary.build_authenticated_event", return_value=SimpleNamespace()), \
         patch("hardware.http_boundary.HardwareAccessService") as service:
        service.return_value.ingest.return_value = ("processed", "decision")
        result = ingest_simulator_request(headers=_auth_headers(), body=b"{}", presented_secret="secret")
    assert result == ("processed", "decision")
    assert calls[:2] == ["commit", "release"]
    conn.rollback.assert_not_called()
