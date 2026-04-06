from pathlib import Path
from unittest.mock import patch

from app.utils.utils import (
    atomic_write_bytes,
    ensure_dir,
    read_json,
    read_text,
    write_json,
    write_text,
)


def test_ensure_dir_creates_directory_and_returns_path(tmp_path):
    path = tmp_path / "nested" / "dir"

    result = ensure_dir(path)

    assert result == path
    assert result.exists()
    assert result.is_dir()


def test_ensure_dir_accepts_string_path(tmp_path):
    path = tmp_path / "string-dir"

    result = ensure_dir(str(path))

    assert result == path
    assert path.exists()
    assert path.is_dir()


def test_read_text_reads_utf8_file(tmp_path):
    path = tmp_path / "example.txt"
    path.write_text("hello world", encoding="utf-8")

    result = read_text(path)

    assert result == "hello world"


def test_write_text_writes_utf8_file(tmp_path):
    path = tmp_path / "example.txt"

    write_text(path, "hello world")

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello world"


def test_write_text_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "example.txt"

    write_text(path, "hello world")

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello world"


def test_read_json_reads_json_object_from_disk(tmp_path):
    path = tmp_path / "example.json"
    path.write_text('{"name": "mike", "count": 3}', encoding="utf-8")

    result = read_json(path)

    assert result == {"name": "mike", "count": 3}


def test_write_json_writes_pretty_utf8_json(tmp_path):
    path = tmp_path / "example.json"
    data = {"name": "mike", "count": 3}

    write_json(path, data)

    assert path.exists()
    assert read_json(path) == data
    text = path.read_text(encoding="utf-8")
    assert text == '{\n  "name": "mike",\n  "count": 3\n}'


def test_write_json_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "example.json"

    write_json(path, {"ok": True})

    assert path.exists()
    assert read_json(path) == {"ok": True}


def test_write_json_preserves_unicode_characters(tmp_path):
    path = tmp_path / "unicode.json"

    write_json(path, {"title": "Björk", "symbol": "🎵"})

    text = path.read_text(encoding="utf-8")
    assert "Björk" in text
    assert "🎵" in text
    assert "\\u" not in text


def test_atomic_write_bytes_writes_file_contents(tmp_path):
    path = tmp_path / "file.bin"

    atomic_write_bytes(path, b"abc123")

    assert path.exists()
    assert path.read_bytes() == b"abc123"


def test_atomic_write_bytes_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "file.bin"

    atomic_write_bytes(path, b"abc123")

    assert path.exists()
    assert path.read_bytes() == b"abc123"


def test_atomic_write_bytes_replaces_existing_file_contents(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"old-data")

    atomic_write_bytes(path, b"new-data")

    assert path.read_bytes() == b"new-data"


def test_atomic_write_bytes_uses_temp_file_and_os_replace(tmp_path):
    path = tmp_path / "file.bin"

    with patch("app.utils.utils.os.replace") as mock_replace:
        atomic_write_bytes(path, b"abc123")

    temp_path = path.with_suffix(path.suffix + ".tmp")
    mock_replace.assert_called_once_with(temp_path, path)
    assert temp_path.exists()
    assert temp_path.read_bytes() == b"abc123"