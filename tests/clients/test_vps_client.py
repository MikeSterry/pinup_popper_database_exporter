# tests/clients/test_vps_client.py

from unittest.mock import Mock

from app.clients.vps_client import VpsClient


def test_fetch_last_updated_epoch_ms_returns_integer_from_text_response():
    http = Mock()
    http.get_text.return_value = "1743811200000"

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        puplookup_url="https://example.com/puplookup.csv",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    result = client.fetch_last_updated_epoch_ms()

    assert result == 1743811200000
    http.get_text.assert_called_once_with("https://example.com/lastUpdated.json")


def test_fetch_last_updated_epoch_ms_strips_whitespace_before_casting_to_int():
    http = Mock()
    http.get_text.return_value = "  \n1743811200000 \r\n"

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        puplookup_url="https://example.com/puplookup.csv",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    result = client.fetch_last_updated_epoch_ms()

    assert result == 1743811200000
    http.get_text.assert_called_once_with("https://example.com/lastUpdated.json")


def test_fetch_last_updated_epoch_ms_uses_empty_string_when_http_returns_none():
    http = Mock()
    http.get_text.return_value = None

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        puplookup_url="https://example.com/puplookup.csv",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    try:
        client.fetch_last_updated_epoch_ms()
        assert False, "Expected ValueError to be raised"
    except ValueError:
        pass

    http.get_text.assert_called_once_with("https://example.com/lastUpdated.json")


def test_fetch_puplookup_csv_bytes_returns_bytes_from_http_client():
    http = Mock()
    http.get_bytes.return_value = b"col1,col2\nvalue1,value2\n"

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        puplookup_url="https://example.com/puplookup.csv",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    result = client.fetch_puplookup_csv_bytes()

    assert result == b"col1,col2\nvalue1,value2\n"
    http.get_bytes.assert_called_once_with("https://example.com/puplookup.csv")


def test_fetch_vpsdb_json_bytes_returns_bytes_from_http_client():
    http = Mock()
    http.get_bytes.return_value = b'{"games": []}'

    client = VpsClient(
        http=http,
        last_updated_url="https://example.com/lastUpdated.json",
        puplookup_url="https://example.com/puplookup.csv",
        vpsdb_url="https://example.com/vpsdb.json",
    )

    result = client.fetch_vpsdb_json_bytes()

    assert result == b'{"games": []}'
    http.get_bytes.assert_called_once_with("https://example.com/vpsdb.json")