"""Reusable HTTP client wrapper."""
from __future__ import annotations
from dataclasses import dataclass
import requests
from app.exceptions.custom_exceptions import RemoteFetchError

@dataclass
class HttpClient:
    """Small wrapper around requests for consistent timeouts and errors."""
    timeout_seconds: int

    def get_text(self, url: str) -> str:
        """GET a URL and return response as text."""
        try:
            resp = requests.get(url, timeout=self.timeout_seconds)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            raise RemoteFetchError(f"Failed to fetch text from {url}: {e}") from e

    def get_bytes(self, url: str) -> bytes:
        """GET a URL and return response as bytes."""
        try:
            resp = requests.get(url, timeout=self.timeout_seconds)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            raise RemoteFetchError(f"Failed to fetch bytes from {url}: {e}") from e
