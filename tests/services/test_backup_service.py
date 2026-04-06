# tests/services/test_backup_service.py

from pathlib import Path
from unittest.mock import patch

from app.services.backup_service import BackupService


def test_rotate_if_exists_returns_early_when_output_file_is_missing(tmp_path):
    backups_dir = tmp_path / "backups"
    output_file = tmp_path / "pup_lookup.csv"

    service = BackupService(backups_dir=backups_dir, max_backups=3)

    with patch("app.services.backup_service.shutil.move") as mock_move, patch.object(
        service, "prune_old_backups"
    ) as mock_prune:
        service.rotate_if_exists(output_file)

    assert backups_dir.exists()
    mock_move.assert_not_called()
    mock_prune.assert_not_called()


def test_rotate_if_exists_moves_existing_file_to_timestamped_backup(tmp_path):
    backups_dir = tmp_path / "backups"
    output_file = tmp_path / "pup_lookup.csv"
    output_file.write_text("hello", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=3)

    with patch(
        "app.services.backup_service.datetime.datetime"
    ) as mock_datetime, patch(
        "app.services.backup_service.shutil.move"
    ) as mock_move, patch.object(
        service, "prune_old_backups"
    ) as mock_prune:
        mock_datetime.utcnow.return_value.strftime.return_value = "20260405T120000Z"

        service.rotate_if_exists(output_file)

    expected_rotated = backups_dir / "pup_lookup.20260405T120000Z.csv"

    assert backups_dir.exists()
    mock_move.assert_called_once_with(str(output_file), str(expected_rotated))
    mock_prune.assert_called_once_with("pup_lookup", ".csv")


def test_prune_old_backups_keeps_only_newest_n_files(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    old_backup = backups_dir / "pup_lookup.20260401T000000Z.csv"
    middle_backup = backups_dir / "pup_lookup.20260402T000000Z.csv"
    newest_backup = backups_dir / "pup_lookup.20260403T000000Z.csv"

    old_backup.write_text("old", encoding="utf-8")
    middle_backup.write_text("middle", encoding="utf-8")
    newest_backup.write_text("newest", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=2)
    service.prune_old_backups("pup_lookup", ".csv")

    assert newest_backup.exists()
    assert middle_backup.exists()
    assert not old_backup.exists()


def test_prune_old_backups_does_nothing_when_backup_count_is_within_limit(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    backup_one = backups_dir / "pup_lookup.20260401T000000Z.csv"
    backup_two = backups_dir / "pup_lookup.20260402T000000Z.csv"

    backup_one.write_text("one", encoding="utf-8")
    backup_two.write_text("two", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=2)
    service.prune_old_backups("pup_lookup", ".csv")

    assert backup_one.exists()
    assert backup_two.exists()


def test_prune_old_backups_returns_early_when_max_backups_is_zero(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    backup_one = backups_dir / "pup_lookup.20260401T000000Z.csv"
    backup_two = backups_dir / "pup_lookup.20260402T000000Z.csv"

    backup_one.write_text("one", encoding="utf-8")
    backup_two.write_text("two", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=0)
    service.prune_old_backups("pup_lookup", ".csv")

    assert backup_one.exists()
    assert backup_two.exists()


def test_prune_old_backups_returns_early_when_max_backups_is_negative(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    backup_one = backups_dir / "pup_lookup.20260401T000000Z.csv"
    backup_two = backups_dir / "pup_lookup.20260402T000000Z.csv"

    backup_one.write_text("one", encoding="utf-8")
    backup_two.write_text("two", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=-1)
    service.prune_old_backups("pup_lookup", ".csv")

    assert backup_one.exists()
    assert backup_two.exists()


def test_prune_old_backups_ignores_non_matching_files(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    matching_old = backups_dir / "pup_lookup.20260401T000000Z.csv"
    matching_new = backups_dir / "pup_lookup.20260402T000000Z.csv"
    different_stem = backups_dir / "other_file.20260403T000000Z.csv"
    different_suffix = backups_dir / "pup_lookup.20260404T000000Z.json"

    matching_old.write_text("old", encoding="utf-8")
    matching_new.write_text("new", encoding="utf-8")
    different_stem.write_text("other", encoding="utf-8")
    different_suffix.write_text("json", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=1)
    service.prune_old_backups("pup_lookup", ".csv")

    assert not matching_old.exists()
    assert matching_new.exists()
    assert different_stem.exists()
    assert different_suffix.exists()


def test_prune_old_backups_swallows_unlink_errors_and_continues(tmp_path):
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    old_backup = backups_dir / "pup_lookup.20260401T000000Z.csv"
    middle_backup = backups_dir / "pup_lookup.20260402T000000Z.csv"
    newest_backup = backups_dir / "pup_lookup.20260403T000000Z.csv"

    old_backup.write_text("old", encoding="utf-8")
    middle_backup.write_text("middle", encoding="utf-8")
    newest_backup.write_text("newest", encoding="utf-8")

    service = BackupService(backups_dir=backups_dir, max_backups=1)

    original_unlink = Path.unlink

    def unlink_side_effect(self, missing_ok=False):
        if self == middle_backup:
            raise OSError("cannot delete")
        return original_unlink(self, missing_ok=missing_ok)

    with patch("pathlib.Path.unlink", autospec=True, side_effect=unlink_side_effect):
        service.prune_old_backups("pup_lookup", ".csv")

    assert newest_backup.exists()
    assert middle_backup.exists()
    assert not old_backup.exists()