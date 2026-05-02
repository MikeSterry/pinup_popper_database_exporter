from pathlib import Path

from app.services.sync_service import (
    LAST_UPDATED_LOCAL_NAME,
    VPSDB_LOCAL_NAME,
    SyncResult,
    SyncService,
)


class DummyVpsClient:
    def __init__(self, remote_epoch_ms=2000, vpsdb_bytes=b"[]"):
        self.remote_epoch_ms = remote_epoch_ms
        self.vpsdb_bytes = vpsdb_bytes
        self.last_updated_calls = 0
        self.vpsdb_calls = 0

    def fetch_last_updated_epoch_ms(self):
        self.last_updated_calls += 1
        return self.remote_epoch_ms

    def fetch_vpsdb_json_bytes(self):
        self.vpsdb_calls += 1
        return self.vpsdb_bytes


def test_sync_result_dataclass_fields():
    result = SyncResult(
        updated=True,
        remote_epoch_ms=200,
        local_epoch_ms=100,
    )

    assert result.updated is True
    assert result.remote_epoch_ms == 200
    assert result.local_epoch_ms == 100


def test_ensure_local_cache_does_nothing_when_required_files_exist(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / VPSDB_LOCAL_NAME).write_bytes(b"[]")
    (data_dir / LAST_UPDATED_LOCAL_NAME).write_text("1000", encoding="utf-8")

    client = DummyVpsClient(remote_epoch_ms=2000)
    service = SyncService(data_dir=data_dir, client=client)

    service.ensure_local_cache()

    assert client.last_updated_calls == 0
    assert client.vpsdb_calls == 0
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "1000"


def test_ensure_local_cache_downloads_when_missing_files(tmp_path):
    data_dir = tmp_path / "data"

    client = DummyVpsClient(
        remote_epoch_ms=3000,
        vpsdb_bytes=b'[{"id":"game-1"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    service.ensure_local_cache()

    assert client.last_updated_calls == 1
    assert client.vpsdb_calls == 1
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"game-1"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "3000"


def test_check_and_sync_downloads_when_remote_is_newer(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / VPSDB_LOCAL_NAME).write_bytes(b"[]")
    (data_dir / LAST_UPDATED_LOCAL_NAME).write_text("1000", encoding="utf-8")

    client = DummyVpsClient(
        remote_epoch_ms=2000,
        vpsdb_bytes=b'[{"id":"updated"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    result = service.check_and_sync()

    assert result == SyncResult(
        updated=True,
        remote_epoch_ms=2000,
        local_epoch_ms=1000,
    )

    assert client.last_updated_calls == 1
    assert client.vpsdb_calls == 1
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"updated"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "2000"


def test_check_and_sync_does_not_download_when_remote_is_not_newer(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / VPSDB_LOCAL_NAME).write_bytes(b'[{"id":"local"}]')
    (data_dir / LAST_UPDATED_LOCAL_NAME).write_text("2000", encoding="utf-8")

    client = DummyVpsClient(
        remote_epoch_ms=2000,
        vpsdb_bytes=b'[{"id":"remote"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    result = service.check_and_sync()

    assert result == SyncResult(
        updated=False,
        remote_epoch_ms=2000,
        local_epoch_ms=2000,
    )

    assert client.last_updated_calls == 1
    assert client.vpsdb_calls == 0
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"local"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "2000"


def test_check_and_sync_downloads_when_vpsdb_missing_even_if_epoch_matches(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / LAST_UPDATED_LOCAL_NAME).write_text("2000", encoding="utf-8")

    client = DummyVpsClient(
        remote_epoch_ms=2000,
        vpsdb_bytes=b'[{"id":"restored"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    result = service.check_and_sync()

    assert result == SyncResult(
        updated=True,
        remote_epoch_ms=2000,
        local_epoch_ms=2000,
    )

    assert client.last_updated_calls == 1
    assert client.vpsdb_calls == 1
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"restored"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "2000"


def test_check_and_sync_treats_bad_local_epoch_as_zero(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / VPSDB_LOCAL_NAME).write_bytes(b"[]")
    (data_dir / LAST_UPDATED_LOCAL_NAME).write_text("not-a-number", encoding="utf-8")

    client = DummyVpsClient(
        remote_epoch_ms=5000,
        vpsdb_bytes=b'[{"id":"updated"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    result = service.check_and_sync()

    assert result == SyncResult(
        updated=True,
        remote_epoch_ms=5000,
        local_epoch_ms=0,
    )

    assert client.last_updated_calls == 1
    assert client.vpsdb_calls == 1
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"updated"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "5000"


def test_check_and_sync_creates_data_dir_when_missing(tmp_path):
    data_dir = tmp_path / "missing-data"

    client = DummyVpsClient(
        remote_epoch_ms=7000,
        vpsdb_bytes=b'[{"id":"created"}]',
    )
    service = SyncService(data_dir=data_dir, client=client)

    result = service.check_and_sync()

    assert result == SyncResult(
        updated=True,
        remote_epoch_ms=7000,
        local_epoch_ms=0,
    )

    assert data_dir.exists()
    assert (data_dir / VPSDB_LOCAL_NAME).read_bytes() == b'[{"id":"created"}]'
    assert (data_dir / LAST_UPDATED_LOCAL_NAME).read_text(encoding="utf-8") == "7000"