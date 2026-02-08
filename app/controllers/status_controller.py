"""Status endpoint for UI iframe and API diagnostics."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template, request

from app.utils.utils import read_text

status_bp = Blueprint("status", __name__)

def _epoch_ms_to_iso(epoch_ms: int) -> str:
    """Convert epoch ms to ISO-8601 UTC string."""
    if not epoch_ms:
        return ""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()

@status_bp.route("/status", methods=["GET"])
def status():
    """Status endpoint:
    - HTML (default) suitable for iframe, with ?theme=light|dark|transparent
    - JSON with ?api=1
    """
    settings = current_app.config["APP_SETTINGS"]
    is_api = request.args.get("api") == "1"
    theme = (request.args.get("theme") or "light").lower()
    if theme not in {"light", "dark", "transparent"}:
        theme = "light"

    data_dir = Path(settings.data_dir)
    output_dir = Path(settings.output_dir)

    last_updated_path = data_dir / "lastUpdated.json"
    local_epoch = 0
    if last_updated_path.exists():
        try:
            local_epoch = int(read_text(last_updated_path).strip())
        except Exception:
            local_epoch = 0

    output_path = output_dir / settings.output_filename
    output_mtime = int(output_path.stat().st_mtime * 1000) if output_path.exists() else 0

    payload = {
        "app": settings.app_name,
        "log_level": settings.log_level,
        "sync_interval_seconds": settings.sync_interval_seconds,
        "max_backups": settings.max_backups,
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "backups_dir": str(Path(settings.backups_dir)),
        "local_last_updated_epoch_ms": local_epoch,
        "local_last_updated_iso_utc": _epoch_ms_to_iso(local_epoch),
        "output_file": str(output_path),
        "output_file_mtime_epoch_ms": output_mtime,
        "output_file_mtime_iso_utc": _epoch_ms_to_iso(output_mtime),
    }

    if is_api:
        return jsonify(payload), 200

    return render_template("status.html", title="Status", theme=theme, status=payload)
