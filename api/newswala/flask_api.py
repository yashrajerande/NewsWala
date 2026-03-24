"""
NewsWala — Flask API endpoints.

Mount this Blueprint on a Flask app to expose NewsWala over HTTP.

To use, make sure to add api/ to sys.path before importing, e.g.:
    import sys; sys.path.insert(0, "api")

Then in your Flask app:
    from newswala.flask_api import newswala_bp
    app.register_blueprint(newswala_bp, url_prefix="/newswala")

Endpoints:
    POST /newswala/run      — Run the full pipeline (body: {"date": "YYYY-MM-DD"} optional)
    GET  /newswala/latest   — Return the most recent pipeline result
    GET  /newswala/whatsapp — Return just the WhatsApp message + image prompt
    GET  /newswala/health   — Health check
"""

import json
import os
import threading
from datetime import date
from http import HTTPStatus

from flask import Blueprint, Response, request


newswala_bp = Blueprint("newswala", __name__)

# In-memory store for the latest result (thread-safe via lock)
_latest_result: dict = {}
_lock = threading.Lock()
_running = False


def _json_response(data: dict, status: int = 200) -> Response:
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        status=status,
        mimetype="application/json",
    )


@newswala_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return _json_response({
        "status": "ok",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "service": "NewsWala",
    })


@newswala_bp.route("/run", methods=["POST"])
def run_pipeline():
    """
    Run the full NewsWala pipeline.

    Request body (optional JSON):
        { "date": "YYYY-MM-DD" }   — defaults to today if omitted

    Returns the full structured output JSON.
    This is synchronous and may take 30-120 seconds due to web search + LLM calls.
    """
    global _running

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _json_response(
            {"error": "ANTHROPIC_API_KEY environment variable is not set."},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    with _lock:
        if _running:
            return _json_response(
                {"error": "A pipeline run is already in progress. Please wait."},
                HTTPStatus.CONFLICT,
            )
        _running = True

    try:
        body = request.get_json(silent=True) or {}
        run_date = body.get("date") or date.today().isoformat()

        from .supervisor import newswala
        package = newswala(run_date=run_date, verbose=True)

        # Strip the rendered string from the HTTP response (keep JSON clean)
        output = {k: v for k, v in package.items() if k != "_rendered"}

        with _lock:
            global _latest_result
            _latest_result = output

        return _json_response(output)

    except Exception as e:
        return _json_response(
            {"error": str(e)},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    finally:
        with _lock:
            _running = False


@newswala_bp.route("/latest", methods=["GET"])
def latest():
    """Return the most recent pipeline result (from this server session)."""
    with _lock:
        if not _latest_result:
            return _json_response(
                {"error": "No pipeline has been run yet. Call POST /newswala/run first."},
                HTTPStatus.NOT_FOUND,
            )
        return _json_response(_latest_result)


@newswala_bp.route("/whatsapp", methods=["GET"])
def whatsapp_message():
    """Return just the WhatsApp message from the latest run."""
    with _lock:
        if not _latest_result:
            return _json_response({"error": "No result yet."}, HTTPStatus.NOT_FOUND)
        wa = _latest_result.get("whatsapp_output", {})
        return _json_response({
            "main_message": wa.get("main_message", ""),
            "shorter_variant": wa.get("shorter_variant", ""),
            "image_prompt": _latest_result.get("image_output", {}).get("image_prompt", ""),
        })
