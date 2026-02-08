"""Coordinates sync -> backup rotation -> export generation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from flask import Flask

from app.clients.http_client import HttpClient
from app.clients.vps_client import VpsClient
from app.exceptions.custom_exceptions import NoUpdateError
from app.services.sync_service import SyncService
from app.services.export_service import ExportService
from app.services.backup_service import BackupService
from app.utils.logger import get_logger
from app.utils.utils import ensure_dir
from app.utils.constants import SCHEDULED_TRIGGER

log = get_logger(__name__)

@dataclass
class JobResult:
    """Outcome of a run."""
    created: bool
    output_path: Path | None
    message: str

@dataclass
class JobService:
    """High-level orchestration."""
    app: Flask

    def run_sync_and_export(self, trigger: str) -> JobResult:
        """Run sync check and export only if remote has updates."""
        settings = self.app.config["APP_SETTINGS"]

        data_dir = ensure_dir(settings.data_dir)
        output_dir = ensure_dir(settings.output_dir)
        backups_dir = ensure_dir(settings.backups_dir)

        http = HttpClient(timeout_seconds=settings.request_timeout_seconds)
        client = VpsClient(
            http=http,
            last_updated_url=settings.last_updated_url,
            puplookup_url=settings.puplookup_url,
            vpsdb_url=settings.vpsdb_url,
        )

        sync = SyncService(data_dir=data_dir, client=client)
        sync.ensure_local_cache()
        sync_result = sync.check_and_sync()

        if not sync_result.updated:
            msg = f"No updates (local={sync_result.local_epoch_ms}, remote={sync_result.remote_epoch_ms})."
            log.info("Trigger=%s %s", trigger, msg)
        else:
            # Rotate existing output into backups before writing new one.
            backup = BackupService(backups_dir=backups_dir, max_backups=settings.max_backups)
            output_path = output_dir / settings.output_filename
            backup.rotate_if_exists(output_path)

        if trigger == SCHEDULED_TRIGGER and not sync_result.updated:
            # For scheduled runs, skip export if no update to avoid unnecessary work.
            msg = f"Scheduled run skipped export since no updates (local={sync_result.local_epoch_ms}, remote={sync_result.remote_epoch_ms})."
            log.info("Trigger=%s %s", trigger, msg)
            return JobResult(created=False, output_path=None, message=msg)

        log.info("Trigger=%s %s", trigger, "Running export generation.")
        exporter = ExportService(
            data_dir=data_dir,
            output_dir=output_dir,
            output_filename=settings.output_filename,
        )
        created = exporter.generate_output_csv()
        msg = f"Created {created.name} (remote={sync_result.remote_epoch_ms})."
        log.info("Trigger=%s %s", trigger, msg)
        return JobResult(created=True, output_path=created, message=msg)
