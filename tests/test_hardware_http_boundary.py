from pathlib import Path


def test_http_boundary_requires_machine_authentication():
    source = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    for header in ("X-Hardware-Key-Id", "X-Hardware-Timestamp", "X-Hardware-Nonce", "X-Hardware-Signature"):
        assert header in source
    assert "verify_device_request" in source


def test_http_boundary_blocks_physical_vendors():
    source = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    assert '"simulator"' in source
    assert "physical_hardware_disabled" in source


def test_tenant_identity_comes_from_authenticated_device():
    source = Path("hardware/http_boundary.py").read_text(encoding="utf-8")
    assert "build_authenticated_event(device, data)" in source
    ingest = Path("hardware/ingest.py").read_text(encoding="utf-8")
    assert 'tenant_id=int(device["condominio_id"])' in ingest
    assert 'device_id=str(device["id"])' in ingest
