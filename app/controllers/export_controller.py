"""Export endpoint handler."""
from __future__ import annotations
from flask import Blueprint, current_app, jsonify, render_template, request, send_file, make_response
from app.exceptions.custom_exceptions import NoUpdateError, PupExporterError
from app.services.job_service import JobService
from app.utils.constants import EXPORT_PAGE_TITLE, NOTHING_CREATED, CREATED_OK, ERROR_GENERIC
from app.utils.logger import get_logger

log = get_logger(__name__)

export_bp = Blueprint("export", __name__)

def _get_theme() -> str:
    """Get export page theme from query params."""
    theme = (request.args.get("theme") or "light").lower()
    return theme if theme in {"light", "dark", "transparent"} else "light"

@export_bp.route("/export", methods=["GET", "POST"])
def export():
    """Single endpoint:
    - Browser: GET renders HTML with Export button; POST runs export.
    - API: GET /export?api=1 runs export and returns JSON or the CSV (if download=1).
    """
    is_api = request.args.get("api") == "1"
    want_download = request.args.get("download") == "1"
    theme = _get_theme()

    # Browser GET: render page.
    if request.method == "GET" and not is_api:
        return render_template("export.html", title=EXPORT_PAGE_TITLE, theme=theme)

    # Otherwise, run job.
    try:
        result = JobService(current_app).run_sync_and_export(trigger="manual")
        if want_download and result.output_path:
            return send_file(result.output_path, as_attachment=True, download_name=result.output_path.name)
        if is_api:
            return jsonify({"created": True, "message": result.message, "file": str(result.output_path)}), 200
        return render_template("export.html", title=EXPORT_PAGE_TITLE, theme=theme, success=True, message=result.message)
    except NoUpdateError as e:
        if is_api:
            # return jsonify({"created": False, "message": str(e)}), 200
            # 204 No Content: caller can treat this as "nothing changed"
            resp = make_response(("", 204))
            # Optional: include a hint without a body (safe to ignore)
            resp.headers["X-Export-Status"] = "not-modified"
            resp.headers["X-Export-Message"] = str(e)
            return resp
        return render_template("export.html", title=EXPORT_PAGE_TITLE, theme=theme, success=False, message=NOTHING_CREATED)
    except PupExporterError as e:
        log.exception("Known app error during export.")
        if is_api:
            return jsonify({"created": False, "error": str(e)}), 500
        return render_template("export.html", title=EXPORT_PAGE_TITLE, theme=theme, success=False, message=str(e))
    except Exception:
        log.exception("Unexpected error during export.")
        if is_api:
            return jsonify({"created": False, "error": ERROR_GENERIC}), 500
        return render_template("export.html", title=EXPORT_PAGE_TITLE, theme=theme, success=False, message=ERROR_GENERIC), 500
