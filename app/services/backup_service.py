"""Rotate outputs into /backups."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import datetime
import shutil
from app.utils.utils import ensure_dir
from app.utils.logger import get_logger

log = get_logger(__name__)

@dataclass
class BackupService:
    """Handles output rotation and pruning."""
    backups_dir: Path
    max_backups: int

    def rotate_if_exists(self, output_file: Path) -> None:
        """Move an existing output file into backups with a timestamped name."""
        ensure_dir(self.backups_dir)
        if not output_file.exists():
            return

        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
        rotated = self.backups_dir / f"{output_file.stem}.{ts}{output_file.suffix}"
        log.info("Rotating existing output to backup: %s", rotated)
        shutil.move(str(output_file), str(rotated))
        self.prune_old_backups(output_file.stem, output_file.suffix)

    def prune_old_backups(self, stem: str, suffix: str) -> None:
        """Keep only the newest N backups for the given file stem."""
        if self.max_backups <= 0:
            return
        backups = sorted(self.backups_dir.glob(f"{stem}.*{suffix}"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in backups[self.max_backups:]:
            try:
                log.info("Pruning old backup: %s", p)
                p.unlink(missing_ok=True)
            except Exception:
                log.exception("Failed pruning backup: %s", p)
