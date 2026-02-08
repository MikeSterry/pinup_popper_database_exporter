"""Background scheduler that triggers sync/export every N seconds."""
from __future__ import annotations
from dataclasses import dataclass
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logger import get_logger
from app.services.job_service import JobService
from app.utils.constants import SCHEDULED_TRIGGER

log = get_logger(__name__)

@dataclass
class SchedulerService:
    """Starts and manages a background interval job."""
    app: Flask
    _scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """Start scheduler once per process."""
        if self._scheduler:
            return

        settings = self.app.config["APP_SETTINGS"]

        scheduler = BackgroundScheduler(timezone=settings.local_timezeone)
        scheduler.add_job(
            func=lambda: self._run_job_safely(),
            trigger=IntervalTrigger(seconds=settings.sync_interval_seconds),
            id="pup_sync_export",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        self._scheduler = scheduler
        log.info("Scheduler started: every %s seconds", settings.sync_interval_seconds)

    def _run_job_safely(self) -> None:
        """Run scheduled job with app context and exception safety."""
        try:
            with self.app.app_context():
                JobService(self.app).run_sync_and_export(trigger=SCHEDULED_TRIGGER)
        except Exception:
            log.exception("Scheduled sync/export job failed.")
