from pathlib import Path
from unittest.mock import Mock, patch

from app.services.sync_service import (
    LAST_UPDATED_LOCAL_NAME,
    PUPLOOKUP_LOCAL_NAME,
    VPSDB_LOCAL_NAME,
    SyncResult,
    SyncService,
)


def test_sync_result_dataclass_fields():
    result = SyncResult(
        updated=True,
        remote_epoch_ms=200,
        local_epoch_ms=100,
    )

    assert result.updated is True
    assert result.remote_epoch_ms == 200
    assert result.local_epoch_ms == 100


def test_local_last_updated_path_returns_expected_file(tmp_path):
    service = SyncService(data_dir=tmp_path, client=Mock())

    assert service._local_last_updated_path() == tmp_path / LAST_UPDATED_LOCAL_NAME


def test_local_epoch_ms_returns_zero_when_last_updated_file_missing(tmp_path):
    service = SyncService(data_dir=tmp_path, client=Mock())

    assert service._local_epoch_ms() == 0


def test_local_epoch_ms_returns_zero_when_last_updated_file_is_invalid(tmp_path):
    path = tmp_path / LAST_UPDATED_LOCAL_NAME
    path.write_text("not-a-number", encoding="utf-8")

    service = SyncService(data_dir=tmp_path, client=Mock())

    assert service._local_epoch_ms() == 0


def test_local_epoch_ms_returns_parsed_integer_when_file_is_valid(tmp_path):
    path = tmp_path / LAST_UPDATED_LOCAL_NAME
    path.write_text("123456789\n", encoding="utf-8")

    service = SyncService(data_dir=tmp_path, client=Mock())

    assert service._local_epoch_ms() == 123456789


def test_ensure_local_cache_does_nothing_when_all_files_exist(tmp_path):
    for filename in (PUPLOOKUP_LOCAL_NAME, VPSDB_LOCAL_NAME, LAST_UPDATED_LOCAL_NAME):
        (tmp_path / filename).write_text("x", encoding="utf-8")

    client = Mock()
    service = SyncService(data_dir=tmp_path, client=client)

    with patch.object(service, "_download_all") as mock_download_all:
        service.ensure_local_cache()

    client.fetch_last_updated_epoch_ms.assert_not_called()
    mock_download_all.assert_not_called()


def test_ensure_local_cache_downloads_when_any_file_is_missing(tmp_path):
    (tmp_path / PUPLOOKUP_LOCAL_NAME).write_text("x", encoding="utf-8")
    # vpsdb.json missing
    # lastUpdated.json missing

    client = Mock()
    client.fetch_last_updated_epoch_ms.return_value = 987654321

    service = SyncService(data_dir=tmp_path, client=client)

    with patch("app.services.sync_service.ensure_dir") as mock_ensure_dir, patch.object(
        service, "_download_all"
    ) as mock_download_all:
        service.ensure_local_cache()

    mock_ensure_dir.assert_called_once_with(tmp_path)
    client.fetch_last_updated_epoch_ms.assert_called_once_with()
    mock_download_all.assert_called_once_with(987654321)


def test_check_and_sync_downloads_when_local_data_files_are_missing(tmp_path):
    last_updated_path = tmp_path / LAST_UPDATED_LOCAL_NAME
    last_updated_path.write_text("100", encoding="utf-8")
    # missing puplookup.csv and vpsdb.json

    client = Mock()
    client.fetch_last_updated_epoch_ms.return_value = 200

    service = SyncService(data_dir=tmp_path, client=client)

    with patch("app.services.sync_service.ensure_dir") as mock_ensure_dir, patch.object(
        service, "_download_all"
    ) as mock_download_all:
        result = service.check_and_sync()

    assert result == SyncResult(updated=True, remote_epoch_ms=200, local_epoch_ms=100)
    mock_ensure_dir.assert_called_once_with(tmp_path)
    client.fetch_last_updated_epoch_ms.assert_called_once_with()
    mock_download_all.assert_called_once_with(200)


def test_check_and_sync_downloads_when_remote_epoch_is_newer(tmp_path):
    (tmp_path / LAST_UPDATED_LOCAL_NAME).write_text("100", encoding="utf-8")
    (tmp_path / PUPLOOKUP_LOCAL_NAME).write_text("pup", encoding="utf-8")
    (tmp_path / VPSDB_LOCAL_NAME).write_text("vpsdb", encoding="utf-8")

    client = Mock()
    client.fetch_last_updated_epoch_ms.return_value = 250

    service = SyncService(data_dir=tmp_path, client=client)

    with patch("app.services.sync_service.ensure_dir") as mock_ensure_dir, patch.object(
        service, "_download_all"
    ) as mock_download_all:
        result = service.check_and_sync()

    assert result == SyncResult(updated=True, remote_epoch_ms=250, local_epoch_ms=100)
    mock_ensure_dir.assert_called_once_with(tmp_path)
    client.fetch_last_updated_epoch_ms.assert_called_once_with()
    mock_download_all.assert_called_once_with(250)


def test_check_and_sync_does_not_download_when_remote_epoch_is_not_newer(tmp_path):
    (tmp_path / LAST_UPDATED_LOCAL_NAME).write_text("250", encoding="utf-8")
    (tmp_path / PUPLOOKUP_LOCAL_NAME).write_text("pup", encoding="utf-8")
    (tmp_path / VPSDB_LOCAL_NAME).write_text("vpsdb", encoding="utf-8")

    client = Mock()
    client.fetch_last_updated_epoch_ms.return_value = 250

    service = SyncService(data_dir=tmp_path, client=client)

    with patch("app.services.sync_service.ensure_dir") as mock_ensure_dir, patch.object(
        service, "_download_all"
    ) as mock_download_all:
        result = service.check_and_sync()

    assert result == SyncResult(updated=False, remote_epoch_ms=250, local_epoch_ms=250)
    mock_ensure_dir.assert_called_once_with(tmp_path)
    client.fetch_last_updated_epoch_ms.assert_called_once_with()
    mock_download_all.assert_not_called()


def test_check_and_sync_does_not_download_when_remote_epoch_is_older(tmp_path):
    (tmp_path / LAST_UPDATED_LOCAL_NAME).write_text("300", encoding="utf-8")
    (tmp_path / PUPLOOKUP_LOCAL_NAME).write_text("pup", encoding="utf-8")
    (tmp_path / VPSDB_LOCAL_NAME).write_text("vpsdb", encoding="utf-8")

    client = Mock()
    client.fetch_last_updated_epoch_ms.return_value = 250

    service = SyncService(data_dir=tmp_path, client=client)

    with patch.object(service, "_download_all") as mock_download_all:
        result = service.check_and_sync()

    assert result == SyncResult(updated=False, remote_epoch_ms=250, local_epoch_ms=300)
    mock_download_all.assert_not_called()


def test_download_all_writes_all_expected_files(tmp_path):
    client = Mock()
    client.fetch_puplookup_csv_bytes.return_value = b"col1,col2\nvalue1,value2\n"
    client.fetch_vpsdb_json_bytes.return_value = b'{"games": []}'

    service = SyncService(data_dir=tmp_path, client=client)

    with patch("app.services.sync_service.ensure_dir") as mock_ensure_dir:
        service._download_all(remote_epoch_ms=777)

    mock_ensure_dir.assert_called_once_with(tmp_path)
    client.fetch_puplookup_csv_bytes.assert_called_once_with()
    client.fetch_vpsdb_json_bytes.assert_called_once_with()

    assert (tmp_path / PUPLOOKUP_LOCAL_NAME).read_bytes() == b"col1,col2\nvalue1,value2\n"
    assert (tmp_path / VPSDB_LOCAL_NAME).read_bytes() == b'{"games": []}'
    assert (tmp_path / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "777"


def test_download_all_overwrites_existing_files(tmp_path):
    (tmp_path / PUPLOOKUP_LOCAL_NAME).write_text("old pup", encoding="utf-8")
    (tmp_path / VPSDB_LOCAL_NAME).write_text("old vpsdb", encoding="utf-8")
    (tmp_path / LAST_UPDATED_LOCAL_NAME).write_text("111", encoding="utf-8")

    client = Mock()
    client.fetch_puplookup_csv_bytes.return_value = b"new pup"
    client.fetch_vpsdb_json_bytes.return_value = b"new vpsdb"

    service = SyncService(data_dir=tmp_path, client=client)
    service._download_all(remote_epoch_ms=999)

    assert (tmp_path / PUPLOOKUP_LOCAL_NAME).read_bytes() == b"new pup"
    assert (tmp_path / VPSDB_LOCAL_NAME).read_bytes() == b"new vpsdb"
    assert (tmp_path / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "999"