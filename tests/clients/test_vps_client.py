import pytest

from app.clients.vps_client import VpsClient


class DummyHttpClient:
    def __init__(self):
        self.text_by_url = {}
        self.bytes_by_url = {}
        self.get_text_calls = []
        self.get_bytes_calls = []

    def get_text(self, url):
        self.get_text_calls.append(url)
        return self.text_by_url[url]

    def get_bytes(self, url):
        self.get_bytes_calls.append(url)
        return self.bytes_by_url[url]


def test_fetch_last_updated_epoch_ms_returns_int():
    http = DummyHttpClient()
    http.text_by_url["https://example.com/lastUpdated.json"] = "1234567890\n"

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    assert client.fetch_last_updated_epoch_ms() == 1234567890
    assert http.get_text_calls == ["https://example.com/lastUpdated.json"]


def test_fetch_last_updated_epoch_ms_raises_for_invalid_value():
    http = DummyHttpClient()
    http.text_by_url["https://example.com/lastUpdated.json"] = "not-a-number"

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    with pytest.raises(ValueError):
        client.fetch_last_updated_epoch_ms()


def test_fetch_vpsdb_json_bytes_returns_bytes():
    http = DummyHttpClient()
    http.bytes_by_url["https://example.com/vpsdb.json"] = b'[{"id":"game-1"}]'

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    assert client.fetch_vpsdb_json_bytes() == b'[{"id":"game-1"}]'
    assert http.get_bytes_calls == ["https://example.com/vpsdb.json"]