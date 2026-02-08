"""Flask application factory."""
from __future__ import annotations

from flask import Flask
from pathlib import Path

from app.config.settings import Settings
from app.utils.logger import configure_logging, get_logger
from app.controllers.export_controller import export_bp
from app.controllers.health_controller import health_bp
from app.controllers.status_controller import status_bp
from app.services.scheduler_service import SchedulerService
from app.services.job_service import JobService

log = get_logger(__name__)

def create_app() -> Flask:
    """Create and configure the Flask app."""
    app = Flask(__name__, template_folder="templates")

    settings = Settings.from_env()
    app.config["APP_SETTINGS"] = settings

    configure_logging(settings)

    app.register_blueprint(export_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(status_bp)

    SchedulerService(app).start()

    # Startup: if output missing, generate an initial export (best-effort).
    # This ensures the first container boot yields an output file without waiting for the scheduler.
    try:
        out_path = Path(settings.output_dir) / settings.output_filename
        if not out_path.exists():
            log.info("Startup: output missing; generating initial export.")
            JobService(app).run_sync_and_export(trigger="startup")
    except Exception:
        log.exception("Startup export failed (continuing).")

    return app
