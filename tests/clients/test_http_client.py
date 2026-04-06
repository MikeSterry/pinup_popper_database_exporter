# tests/clients/test_http_client.py

from unittest.mock import Mock, patch

import pytest
import requests

from app.clients.http_client import HttpClient
from app.exceptions.custom_exceptions import RemoteFetchError


def test_get_text_returns_response_text():
    client = HttpClient(timeout_seconds=15)

    response = Mock()
    response.text = "hello world"
    response.raise_for_status = Mock()

    with patch("app.clients.http_client.requests.get", return_value=response) as mock_get:
        result = client.get_text("https://example.com/test.txt")

    assert result == "hello world"
    mock_get.assert_called_once_with("https://example.com/test.txt", timeout=15)
    response.raise_for_status.assert_called_once_with()


def test_get_bytes_returns_response_content():
    client = HttpClient(timeout_seconds=20)

    response = Mock()
    response.content = b"abc123"
    response.raise_for_status = Mock()

    with patch("app.clients.http_client.requests.get", return_value=response) as mock_get:
        result = client.get_bytes("https://example.com/file.bin")

    assert result == b"abc123"
    mock_get.assert_called_once_with("https://example.com/file.bin", timeout=20)
    response.raise_for_status.assert_called_once_with()


def test_get_text_raises_remote_fetch_error_when_requests_get_fails():
    client = HttpClient(timeout_seconds=5)

    with patch(
        "app.clients.http_client.requests.get",
        side_effect=requests.exceptions.Timeout("timed out"),
    ) as mock_get:
        with pytest.raises(RemoteFetchError) as exc_info:
            client.get_text("https://example.com/test.txt")

    assert "Failed to fetch text from https://example.com/test.txt" in str(exc_info.value)
    assert "timed out" in str(exc_info.value)
    mock_get.assert_called_once_with("https://example.com/test.txt", timeout=5)


def test_get_bytes_raises_remote_fetch_error_when_requests_get_fails():
    client = HttpClient(timeout_seconds=5)

    with patch(
        "app.clients.http_client.requests.get",
        side_effect=requests.exceptions.ConnectionError("connection failed"),
    ) as mock_get:
        with pytest.raises(RemoteFetchError) as exc_info:
            client.get_bytes("https://example.com/file.bin")

    assert "Failed to fetch bytes from https://example.com/file.bin" in str(exc_info.value)
    assert "connection failed" in str(exc_info.value)
    mock_get.assert_called_once_with("https://example.com/file.bin", timeout=5)


def test_get_text_raises_remote_fetch_error_when_raise_for_status_fails():
    client = HttpClient(timeout_seconds=10)

    response = Mock()
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")

    with patch("app.clients.http_client.requests.get", return_value=response) as mock_get:
        with pytest.raises(RemoteFetchError) as exc_info:
            client.get_text("https://example.com/missing.txt")

    assert "Failed to fetch text from https://example.com/missing.txt" in str(exc_info.value)
    assert "404 Client Error" in str(exc_info.value)
    mock_get.assert_called_once_with("https://example.com/missing.txt", timeout=10)


def test_get_bytes_raises_remote_fetch_error_when_raise_for_status_fails():
    client = HttpClient(timeout_seconds=10)

    response = Mock()
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")

    with patch("app.clients.http_client.requests.get", return_value=response) as mock_get:
        with pytest.raises(RemoteFetchError) as exc_info:
            client.get_bytes("https://example.com/file.bin")

    assert "Failed to fetch bytes from https://example.com/file.bin" in str(exc_info.value)
    assert "500 Server Error" in str(exc_info.value)
    mock_get.assert_called_once_with("https://example.com/file.bin", timeout=10)