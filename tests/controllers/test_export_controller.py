from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from app.controllers.export_controller import _get_theme, export_bp
from app.exceptions.custom_exceptions import NoUpdateError, PupExporterError
from app.utils.constants import ERROR_GENERIC, EXPORT_PAGE_TITLE, NOTHING_CREATED


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.config["APP_SETTINGS"] = SimpleNamespace()
    flask_app.register_blueprint(export_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_get_theme_returns_light_when_missing(app):
    with app.test_request_context("/export"):
        assert _get_theme() == "light"


def test_get_theme_returns_allowed_value_dark(app):
    with app.test_request_context("/export?theme=dark"):
        assert _get_theme() == "dark"


def test_get_theme_returns_allowed_value_transparent(app):
    with app.test_request_context("/export?theme=transparent"):
        assert _get_theme() == "transparent"


def test_get_theme_falls_back_to_light_for_invalid_value(app):
    with app.test_request_context("/export?theme=banana"):
        assert _get_theme() == "light"


def test_export_get_renders_browser_page(client):
    with patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered export page",
    ) as mock_render:
        response = client.get("/export")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered export page"
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="light",
    )


def test_export_get_renders_browser_page_with_dark_theme(client):
    with patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered export page",
    ) as mock_render:
        response = client.get("/export?theme=dark")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered export page"
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="dark",
    )


def test_export_post_renders_success_for_browser(client):
    result = SimpleNamespace(
        created=True,
        output_path=Path("/tmp/pup_lookup.csv"),
        message="Created pup_lookup.csv (remote=123456789).",
    )

    with patch("app.controllers.export_controller.JobService") as mock_job_service, patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered success page",
    ) as mock_render:
        mock_job_service.return_value.run_sync_and_export.return_value = result

        response = client.post("/export")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered success page"
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="light",
        success=True,
        message=result.message,
    )


def test_export_api_returns_json_success(client):
    result = SimpleNamespace(
        created=True,
        output_path=Path("/tmp/pup_lookup.csv"),
        message="Created pup_lookup.csv (remote=123456789).",
    )

    with patch("app.controllers.export_controller.JobService") as mock_job_service:
        mock_job_service.return_value.run_sync_and_export.return_value = result

        response = client.get("/export?api=1")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {
        "created": True,
        "message": result.message,
        "file": str(result.output_path),
    }
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")


def test_export_api_download_returns_file_response(client, tmp_path):
    output_file = tmp_path / "pup_lookup.csv"
    output_file.write_text("col1,col2\nvalue1,value2\n", encoding="utf-8")

    result = SimpleNamespace(
        created=True,
        output_path=output_file,
        message="Created pup_lookup.csv (remote=123456789).",
    )

    with patch("app.controllers.export_controller.JobService") as mock_job_service:
        mock_job_service.return_value.run_sync_and_export.return_value = result

        response = client.get("/export?api=1&download=1")

    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert "pup_lookup.csv" in response.headers["Content-Disposition"]
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")


def test_export_browser_handles_no_update_error(client):
    with patch("app.controllers.export_controller.JobService") as mock_job_service, patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered no-update page",
    ) as mock_render:
        mock_job_service.return_value.run_sync_and_export.side_effect = NoUpdateError("No updates found.")

        response = client.post("/export")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered no-update page"
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="light",
        success=False,
        message=NOTHING_CREATED,
    )


def test_export_api_handles_no_update_error_with_204_and_headers(client):
    message = "No updates found."

    with patch("app.controllers.export_controller.JobService") as mock_job_service:
        mock_job_service.return_value.run_sync_and_export.side_effect = NoUpdateError(message)

        response = client.get("/export?api=1")

    assert response.status_code == 204
    assert response.get_data(as_text=True) == ""
    assert response.headers["X-Export-Status"] == "not-modified"
    assert response.headers["X-Export-Message"] == message
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")


def test_export_browser_handles_known_app_error(client):
    with patch("app.controllers.export_controller.JobService") as mock_job_service, patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered known-error page",
    ) as mock_render:
        mock_job_service.return_value.run_sync_and_export.side_effect = PupExporterError("Known failure")

        response = client.post("/export")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "rendered known-error page"
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="light",
        success=False,
        message="Known failure",
    )


def test_export_api_handles_known_app_error(client):
    with patch("app.controllers.export_controller.JobService") as mock_job_service:
        mock_job_service.return_value.run_sync_and_export.side_effect = PupExporterError("Known failure")

        response = client.get("/export?api=1")

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json() == {
        "created": False,
        "error": "Known failure",
    }
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")


def test_export_browser_handles_unexpected_error(client):
    with patch("app.controllers.export_controller.JobService") as mock_job_service, patch(
        "app.controllers.export_controller.render_template",
        return_value="rendered generic-error page",
    ) as mock_render:
        mock_job_service.return_value.run_sync_and_export.side_effect = RuntimeError("Boom")

        response = client.post("/export")

    assert response.status_code == 500
    assert response.get_data(as_text=True) == "rendered generic-error page"
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")
    mock_render.assert_called_once_with(
        "export.html",
        title=EXPORT_PAGE_TITLE,
        theme="light",
        success=False,
        message=ERROR_GENERIC,
    )


def test_export_api_handles_unexpected_error(client):
    with patch("app.controllers.export_controller.JobService") as mock_job_service:
        mock_job_service.return_value.run_sync_and_export.side_effect = RuntimeError("Boom")

        response = client.get("/export?api=1")

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json() == {
        "created": False,
        "error": ERROR_GENERIC,
    }
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(trigger="manual")