"""Sync service: checks lastUpdated.json and refreshes local cached VPS data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.clients.vps_client import VpsClient
from app.utils.logger import get_logger
from app.utils.utils import atomic_write_bytes, ensure_dir, read_text, write_text

log = get_logger(__name__)

LAST_UPDATED_LOCAL_NAME = "lastUpdated.json"
VPSDB_LOCAL_NAME = "vpsdb.json"


@dataclass
class SyncResult:
    """Outcome of a sync check."""

    updated: bool
    remote_epoch_ms: int
    local_epoch_ms: int


@dataclass
class SyncService:
    """Keeps a local cache of remote VPS files and refreshes when updated."""

    data_dir: Path
    client: VpsClient

    def _local_last_updated_path(self) -> Path:
        """Path to local lastUpdated.json."""
        return self.data_dir / LAST_UPDATED_LOCAL_NAME

    def _local_epoch_ms(self) -> int:
        """Read local epoch-ms, or 0 if missing/unreadable."""
        path = self._local_last_updated_path()

        if not path.exists():
            return 0

        try:
            return int(read_text(path).strip())
        except Exception:
            log.error("Failed to read local epoch-ms from %s", path)
            return 0

    def ensure_local_cache(self) -> None:
        """On initial run, pull remote files if they are not present locally."""
        ensure_dir(self.data_dir)
        log.info("Syncing local cache: %s", self.data_dir)

        required_files = (
            VPSDB_LOCAL_NAME,
            LAST_UPDATED_LOCAL_NAME,
        )

        missing_any = any(not (self.data_dir / fname).exists() for fname in required_files)

        if not missing_any:
            log.info("Local cache exists.")
            return

        log.info("Local cache missing files; downloading initial data set.")
        remote_epoch = self.client.fetch_last_updated_epoch_ms()
        self._download_all(remote_epoch)

    def check_and_sync(self) -> SyncResult:
        """Check remote epoch-ms and download files if remote is newer."""
        ensure_dir(self.data_dir)

        local_epoch = self._local_epoch_ms()
        remote_epoch = self.client.fetch_last_updated_epoch_ms()

        log.info("Sync check: local=%s remote=%s", local_epoch, remote_epoch)

        missing_any = not (self.data_dir / VPSDB_LOCAL_NAME).exists()

        if missing_any:
            log.info("Local VPS DB missing; treating as update.")
            self._download_all(remote_epoch)
            return SyncResult(
                updated=True,
                remote_epoch_ms=remote_epoch,
                local_epoch_ms=local_epoch,
            )

        if remote_epoch > local_epoch:
            self._download_all(remote_epoch)
            return SyncResult(
                updated=True,
                remote_epoch_ms=remote_epoch,
                local_epoch_ms=local_epoch,
            )

        return SyncResult(
            updated=False,
            remote_epoch_ms=remote_epoch,
            local_epoch_ms=local_epoch,
        )

    def _download_all(self, remote_epoch_ms: int) -> None:
        """Download vpsdb.json and update local lastUpdated.json."""
        ensure_dir(self.data_dir)
        log.info("Downloading VPS DB cache into: %s", self.data_dir)

        vpsdb_bytes = self.client.fetch_vpsdb_json_bytes()

        atomic_write_bytes(self.data_dir / VPSDB_LOCAL_NAME, vpsdb_bytes)
        write_text(self._local_last_updated_path(), str(remote_epoch_ms))

        log.info("Downloaded/updated local VPS DB cache.")