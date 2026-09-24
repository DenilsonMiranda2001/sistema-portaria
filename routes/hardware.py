import os
from flask import Blueprint, jsonify, request, g
from hardware.http_boundary import HardwareHttpError, ingest_simulator_request


hardware_bp = Blueprint("hardware", __name__, url_prefix="/api/hardware")
MAX_HARDWARE_BODY_BYTES = 32 * 1024


@hardware_bp.post("/simulator/events")
def simulator_event():
    if os.getenv("HARDWARE_SIMULATOR_HTTP_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
        return jsonify(error="not_found", request_id=getattr(g, "request_id", None)), 404
    if request.content_length is not None and request.content_length > MAX_HARDWARE_BODY_BYTES:
        return jsonify(error="payload_too_large", request_id=getattr(g, "request_id", None)), 413
    body = request.get_data(cache=False, as_text=False)
    if len(body) > MAX_HARDWARE_BODY_BYTES:
        return jsonify(error="payload_too_large", request_id=getattr(g, "request_id", None)), 413
    try:
        processed, decision = ingest_simulator_request(
            headers=request.headers,
            body=body,
            presented_secret=request.headers.get("X-Hardware-Secret", ""),
        )
    except HardwareHttpError as exc:
        return jsonify(error=exc.code, request_id=getattr(g, "request_id", None)), exc.status
    return jsonify(
        accepted=bool(processed.accepted),
        duplicate=bool(processed.duplicate),
        granted=bool(decision.granted) if decision is not None else None,
        request_id=getattr(g, "request_id", None),
    ), 202
