"""Sync service: checks lastUpdated.json and refreshes local cached data."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from app.clients.vps_client import VpsClient
from app.utils.utils import ensure_dir, read_text, write_text, atomic_write_bytes
from app.utils.logger import get_logger

log = get_logger(__name__)

LAST_UPDATED_LOCAL_NAME = "lastUpdated.json"
PUPLOOKUP_LOCAL_NAME = "puplookup.csv"
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
        p = self._local_last_updated_path()
        if not p.exists():
            return 0
        try:
            return int(read_text(p).strip())
        except Exception:
            return 0

    def ensure_local_cache(self) -> None:
        """On initial run, pull remote files if they're not present locally."""
        ensure_dir(self.data_dir)

        # If either data file is missing, force a download.
        need = False
        for fname in (PUPLOOKUP_LOCAL_NAME, VPSDB_LOCAL_NAME, LAST_UPDATED_LOCAL_NAME):
            if not (self.data_dir / fname).exists():
                need = True
                break
        if not need:
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

        # If local cache is missing critical files, treat as update.
        missing_any = any(not (self.data_dir / f).exists() for f in (PUPLOOKUP_LOCAL_NAME, VPSDB_LOCAL_NAME))
        if missing_any:
            log.info("Local data missing; treating as update.")
            self._download_all(remote_epoch)
            return SyncResult(updated=True, remote_epoch_ms=remote_epoch, local_epoch_ms=local_epoch)

        if remote_epoch > local_epoch:
            self._download_all(remote_epoch)
            return SyncResult(updated=True, remote_epoch_ms=remote_epoch, local_epoch_ms=local_epoch)

        return SyncResult(updated=False, remote_epoch_ms=remote_epoch, local_epoch_ms=local_epoch)

    def _download_all(self, remote_epoch_ms: int) -> None:
        """Download puplookup.csv and vpsdb.json and update local lastUpdated.json."""
        ensure_dir(self.data_dir)

        pup_bytes = self.client.fetch_puplookup_csv_bytes()
        vpsdb_bytes = self.client.fetch_vpsdb_json_bytes()

        atomic_write_bytes(self.data_dir / PUPLOOKUP_LOCAL_NAME, pup_bytes)
        atomic_write_bytes(self.data_dir / VPSDB_LOCAL_NAME, vpsdb_bytes)
        write_text(self._local_last_updated_path(), str(remote_epoch_ms))

        log.info("Downloaded/updated local cache.")
