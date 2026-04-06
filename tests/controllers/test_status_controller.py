from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from app.controllers.status_controller import _epoch_ms_to_custom, status_bp


@pytest.fixture
def app(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    backups_dir = tmp_path / "backups"

    data_dir.mkdir()
    output_dir.mkdir()
    backups_dir.mkdir()

    settings = SimpleNamespace(
        app_name="Pinup Popper Database Exporter",
        log_level="INFO",
        sync_interval_seconds=300,
        max_backups=5,
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        backups_dir=str(backups_dir),
        output_filename="pup_lookup.csv",
        local_timezeone="America/Chicago",  # match current code typo exactly
    )

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.config["APP_SETTINGS"] = settings
    flask_app.register_blueprint(status_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_epoch_ms_to_custom_returns_empty_string_for_zero():
    assert _epoch_ms_to_custom(0, "America/Chicago") == ""


def test_epoch_ms_to_custom_formats_timestamp():
    result = _epoch_ms_to_custom(1704067200000, "America/Chicago")
    assert result
    assert len(result) == 16
    assert "-" in result
    assert ":" in result


def test_status_api_returns_expected_payload_when_files_missing(client, app):
    response = client.get("/status?api=1")

    assert response.status_code == 200
    assert response.is_json

    payload = response.get_json()
    settings = app.config["APP_SETTINGS"]

    assert payload["app"] == settings.app_name
    assert payload["log_level"] == settings.log_level
    assert payload["sync_interval_seconds"] == settings.sync_interval_seconds
    assert payload["max_backups"] == settings.max_backups
    assert payload["data_dir"] == settings.data_dir
    assert payload["output_dir"] == settings.output_dir
    assert payload["backups_dir"] == settings.backups_dir
    assert payload["local_last_updated_epoch_ms"] == 0
    assert payload["local_last_updated_iso_utc"] == ""
    assert payload["output_file"] == str(Path(settings.output_dir) / settings.output_filename)
    assert payload["output_file_mtime_epoch_ms"] == 0
    assert payload["output_file_mtime_iso_utc"] == ""


def test_status_api_reads_last_updated_and_output_file_metadata(client, app):
    settings = app.config["APP_SETTINGS"]

    last_updated_path = Path(settings.data_dir) / "lastUpdated.json"
    last_updated_path.write_text("1704067200000\n", encoding="utf-8")

    output_path = Path(settings.output_dir) / settings.output_filename
    output_path.write_text("col1,col2\nvalue1,value2\n", encoding="utf-8")

    response = client.get("/status?api=1")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["local_last_updated_epoch_ms"] == 1704067200000
    assert payload["local_last_updated_iso_utc"] == _epoch_ms_to_custom(
        1704067200000,
        settings.local_timezeone,
    )
    assert payload["output_file"] == str(output_path)
    assert payload["output_file_mtime_epoch_ms"] > 0
    assert payload["output_file_mtime_iso_utc"] == _epoch_ms_to_custom(
        payload["output_file_mtime_epoch_ms"],
        settings.local_timezeone,
    )


def test_status_api_uses_zero_when_last_updated_file_is_invalid(client, app):
    settings = app.config["APP_SETTINGS"]

    last_updated_path = Path(settings.data_dir) / "lastUpdated.json"
    last_updated_path.write_text("not-a-number", encoding="utf-8")

    response = client.get("/status?api=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["local_last_updated_epoch_ms"] == 0
    assert payload["local_last_updated_iso_utc"] == ""


def test_status_html_renders_template_with_default_light_theme(client):
    with patch(
        "app.controllers.status_controller.render_template",
        return_value="rendered status page",
    ) as mock_render:
        response = client.get("/status")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered status page"

    args, kwargs = mock_render.call_args
    assert args[0] == "status.html"
    assert kwargs["title"] == "Status"
    assert kwargs["theme"] == "light"
    assert "status" in kwargs


def test_status_html_renders_template_with_dark_theme(client):
    with patch(
        "app.controllers.status_controller.render_template",
        return_value="rendered status page",
    ) as mock_render:
        response = client.get("/status?theme=dark")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered status page"

    args, kwargs = mock_render.call_args
    assert args[0] == "status.html"
    assert kwargs["theme"] == "dark"


def test_status_html_invalid_theme_falls_back_to_light(client):
    with patch(
        "app.controllers.status_controller.render_template",
        return_value="rendered status page",
    ) as mock_render:
        response = client.get("/status?theme=banana")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered status page"

    args, kwargs = mock_render.call_args
    assert args[0] == "status.html"
    assert kwargs["theme"] == "light"


def test_status_only_allows_get(client):
    response = client.post("/status")
    assert response.status_code == 405