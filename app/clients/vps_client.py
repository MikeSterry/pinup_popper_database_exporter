"""Client for VPS GitHub Pages endpoints."""
from __future__ import annotations
from dataclasses import dataclass
from app.clients.http_client import HttpClient

@dataclass
class VpsClient:
    """Client for VPS DB remote resources."""
    http: HttpClient
    last_updated_url: str
    puplookup_url: str
    vpsdb_url: str

    def fetch_last_updated_epoch_ms(self) -> int:
        """Fetch lastUpdated.json which is a single epoch-ms number."""
        txt = (self.http.get_text(self.last_updated_url) or "").strip()
        return int(txt)

    def fetch_puplookup_csv_bytes(self) -> bytes:
        """Fetch puplookup.csv as bytes."""
        return self.http.get_bytes(self.puplookup_url)

    def fetch_vpsdb_json_bytes(self) -> bytes:
        """Fetch vpsdb.json as bytes."""
        return self.http.get_bytes(self.vpsdb_url)
