"""Centralized configuration with environment-variable overrides."""
from dataclasses import dataclass
import os

def _env(key: str, default: str) -> str:
    """Read an environment variable with a fallback."""
    return os.getenv(key, default)

def _env_int(key: str, default: int) -> int:
    """Read an integer env var with fallback."""
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

@dataclass(frozen=True)
class Settings:
    """Application settings (override via env vars)."""
    app_name: str
    log_level: str
    request_timeout_seconds: int

    last_updated_url: str
    puplookup_url: str
    vpsdb_url: str

    data_dir: str
    output_dir: str
    backups_dir: str

    output_filename: str
    sync_interval_seconds: int
    max_backups: int

    local_timezeone: str

    @staticmethod
    def from_env() -> "Settings":
        """Build settings from environment variables."""
        return Settings(
            app_name=_env("APP_NAME", "pup-exporter"),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 60),

            last_updated_url=_env("LAST_UPDATED_URL", "https://virtualpinballspreadsheet.github.io/vps-db/lastUpdated.json"),
            puplookup_url=_env("PUPLOOKUP_URL", "https://virtualpinballspreadsheet.github.io/vps-db/db/puplookup.csv"),
            vpsdb_url=_env("VPSDB_URL", "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json"),

            data_dir=_env("DATA_DIR", "/data"),
            output_dir=_env("OUTPUT_DIR", "/output"),
            backups_dir=_env("BACKUPS_DIR", "/backups"),

            output_filename=_env("OUTPUT_FILENAME", "puplookup.csv"),
            sync_interval_seconds=_env_int("SYNC_INTERVAL_SECONDS", 3600),
            max_backups=_env_int("MAX_BACKUPS", 10),

            local_timezeone=_env("LOCAL_TIMEZONE", "America/Chicago"),
        )
