from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.job_service import JobResult, JobService
from app.utils.constants import SCHEDULED_TRIGGER


def build_settings(tmp_path):
    return SimpleNamespace(
        data_dir=str(tmp_path / "data"),
        output_dir=str(tmp_path / "output"),
        backups_dir=str(tmp_path / "backups"),
        request_timeout_seconds=15,
        last_updated_url="https://example.com/lastUpdated.json",
        vpsdb_url="https://example.com/vpsdb.json",
        output_filename="puplookup_out.csv",
        max_backups=3,
    )


def build_app(settings):
    app = Mock()
    app.config = {"APP_SETTINGS": settings}
    return app


def test_job_result_dataclass_fields():
    result = JobResult(
        created=True,
        output_path=Path("/tmp/output.csv"),
        message="done",
    )

    assert result.created is True
    assert result.output_path == Path("/tmp/output.csv")
    assert result.message == "done"


def test_run_sync_and_export_creates_output_when_updated(tmp_path):
    settings = build_settings(tmp_path)
    app = build_app(settings)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"
    expected_output_path = output_dir / settings.output_filename

    sync_result = SimpleNamespace(
        updated=True,
        local_epoch_ms=111,
        remote_epoch_ms=222,
    )

    with patch("app.services.job_service.ensure_dir", side_effect=[data_dir, output_dir, backups_dir]) as mock_ensure_dir, \
        patch("app.services.job_service.HttpClient") as mock_http_client, \
        patch("app.services.job_service.VpsClient") as mock_vps_client, \
        patch("app.services.job_service.SyncService") as mock_sync_service, \
        patch("app.services.job_service.BackupService") as mock_backup_service, \
        patch("app.services.job_service.ExportService") as mock_export_service:

        mock_sync_service.return_value.check_and_sync.return_value = sync_result
        mock_export_service.return_value.generate_output_csv.return_value = expected_output_path

        result = JobService(app).run_sync_and_export(trigger="manual")

    assert result == JobResult(
        created=True,
        output_path=expected_output_path,
        message="Created puplookup_out.csv (remote=222).",
    )

    assert mock_ensure_dir.call_count == 3
    mock_ensure_dir.assert_any_call(settings.data_dir)
    mock_ensure_dir.assert_any_call(settings.output_dir)
    mock_ensure_dir.assert_any_call(settings.backups_dir)

    mock_http_client.assert_called_once_with(timeout_seconds=settings.request_timeout_seconds)

    mock_vps_client.assert_called_once_with(
        http=mock_http_client.return_value,
        last_updated_url=settings.last_updated_url,
        vpsdb_url=settings.vpsdb_url,
    )

    mock_sync_service.assert_called_once_with(
        data_dir=data_dir,
        client=mock_vps_client.return_value,
    )
    mock_sync_service.return_value.ensure_local_cache.assert_called_once_with()
    mock_sync_service.return_value.check_and_sync.assert_called_once_with()

    mock_backup_service.assert_called_once_with(
        backups_dir=backups_dir,
        max_backups=settings.max_backups,
    )
    mock_backup_service.return_value.rotate_if_exists.assert_called_once_with(expected_output_path)

    mock_export_service.assert_called_once_with(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename=settings.output_filename,
    )
    mock_export_service.return_value.generate_output_csv.assert_called_once_with()


def test_run_sync_and_export_manual_run_still_exports_when_not_updated(tmp_path):
    settings = build_settings(tmp_path)
    app = build_app(settings)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"
    expected_output_path = output_dir / settings.output_filename

    sync_result = SimpleNamespace(
        updated=False,
        local_epoch_ms=1000,
        remote_epoch_ms=1000,
    )

    with patch("app.services.job_service.ensure_dir", side_effect=[data_dir, output_dir, backups_dir]), \
        patch("app.services.job_service.HttpClient"), \
        patch("app.services.job_service.VpsClient"), \
        patch("app.services.job_service.SyncService") as mock_sync_service, \
        patch("app.services.job_service.BackupService") as mock_backup_service, \
        patch("app.services.job_service.ExportService") as mock_export_service:

        mock_sync_service.return_value.check_and_sync.return_value = sync_result
        mock_export_service.return_value.generate_output_csv.return_value = expected_output_path

        result = JobService(app).run_sync_and_export(trigger="manual")

    assert result == JobResult(
        created=True,
        output_path=expected_output_path,
        message="Created puplookup_out.csv (remote=1000).",
    )

    mock_sync_service.return_value.ensure_local_cache.assert_called_once_with()
    mock_sync_service.return_value.check_and_sync.assert_called_once_with()

    mock_backup_service.return_value.rotate_if_exists.assert_called_once_with(expected_output_path)
    mock_export_service.return_value.generate_output_csv.assert_called_once_with()


def test_run_sync_and_export_scheduled_run_skips_export_when_not_updated(tmp_path):
    settings = build_settings(tmp_path)
    app = build_app(settings)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"

    sync_result = SimpleNamespace(
        updated=False,
        local_epoch_ms=123,
        remote_epoch_ms=123,
    )

    with patch("app.services.job_service.ensure_dir", side_effect=[data_dir, output_dir, backups_dir]), \
        patch("app.services.job_service.HttpClient"), \
        patch("app.services.job_service.VpsClient"), \
        patch("app.services.job_service.SyncService") as mock_sync_service, \
        patch("app.services.job_service.BackupService") as mock_backup_service, \
        patch("app.services.job_service.ExportService") as mock_export_service:

        mock_sync_service.return_value.check_and_sync.return_value = sync_result

        result = JobService(app).run_sync_and_export(trigger=SCHEDULED_TRIGGER)

    assert result == JobResult(
        created=False,
        output_path=None,
        message="Scheduled run skipped export since no updates (local=123, remote=123).",
    )

    mock_sync_service.return_value.ensure_local_cache.assert_called_once_with()
    mock_sync_service.return_value.check_and_sync.assert_called_once_with()
    mock_backup_service.assert_not_called()
    mock_export_service.assert_not_called()


def test_run_sync_and_export_scheduled_run_exports_when_updated(tmp_path):
    settings = build_settings(tmp_path)
    app = build_app(settings)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"
    expected_output_path = output_dir / settings.output_filename

    sync_result = SimpleNamespace(
        updated=True,
        local_epoch_ms=100,
        remote_epoch_ms=200,
    )

    with patch("app.services.job_service.ensure_dir", side_effect=[data_dir, output_dir, backups_dir]), \
        patch("app.services.job_service.HttpClient"), \
        patch("app.services.job_service.VpsClient"), \
        patch("app.services.job_service.SyncService") as mock_sync_service, \
        patch("app.services.job_service.BackupService") as mock_backup_service, \
        patch("app.services.job_service.ExportService") as mock_export_service:

        mock_sync_service.return_value.check_and_sync.return_value = sync_result
        mock_export_service.return_value.generate_output_csv.return_value = expected_output_path

        result = JobService(app).run_sync_and_export(trigger=SCHEDULED_TRIGGER)

    assert result == JobResult(
        created=True,
        output_path=expected_output_path,
        message="Created puplookup_out.csv (remote=200).",
    )

    mock_backup_service.return_value.rotate_if_exists.assert_called_once_with(expected_output_path)
    mock_export_service.return_value.generate_output_csv.assert_called_once_with()


def test_run_sync_and_export_uses_output_filename_for_rotation_and_exporter(tmp_path):
    settings = build_settings(tmp_path)
    settings.output_filename = "custom_export.csv"
    app = build_app(settings)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"
    expected_output_path = output_dir / settings.output_filename

    sync_result = SimpleNamespace(
        updated=True,
        local_epoch_ms=10,
        remote_epoch_ms=20,
    )

    with patch("app.services.job_service.ensure_dir", side_effect=[data_dir, output_dir, backups_dir]), \
        patch("app.services.job_service.HttpClient"), \
        patch("app.services.job_service.VpsClient"), \
        patch("app.services.job_service.SyncService") as mock_sync_service, \
        patch("app.services.job_service.BackupService") as mock_backup_service, \
        patch("app.services.job_service.ExportService") as mock_export_service:

        mock_sync_service.return_value.check_and_sync.return_value = sync_result
        mock_export_service.return_value.generate_output_csv.return_value = expected_output_path

        result = JobService(app).run_sync_and_export(trigger="manual")

    assert result.output_path == expected_output_path

    mock_backup_service.return_value.rotate_if_exists.assert_called_once_with(expected_output_path)
    mock_export_service.assert_called_once_with(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="custom_export.csv",
    )