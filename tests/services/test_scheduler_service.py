from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from app.services.scheduler_service import SchedulerService
from app.utils.constants import SCHEDULED_TRIGGER


def build_app():
    app = Mock()
    app.config = {
        "APP_SETTINGS": SimpleNamespace(
            local_timezeone="America/Chicago",
            sync_interval_seconds=300,
        )
    }
    return app


def test_start_creates_and_starts_scheduler_once():
    app = build_app()

    with patch("app.services.scheduler_service.BackgroundScheduler") as mock_scheduler_cls, \
         patch("app.services.scheduler_service.IntervalTrigger") as mock_interval_trigger:

        scheduler = mock_scheduler_cls.return_value
        trigger = mock_interval_trigger.return_value

        service = SchedulerService(app=app)
        service.start()

    mock_scheduler_cls.assert_called_once_with(timezone="America/Chicago")
    mock_interval_trigger.assert_called_once_with(seconds=300)
    scheduler.add_job.assert_called_once()

    _, kwargs = scheduler.add_job.call_args
    assert callable(kwargs["func"])
    assert kwargs["trigger"] == trigger
    assert kwargs["id"] == "pup_sync_export"
    assert kwargs["replace_existing"] is True
    assert kwargs["max_instances"] == 1
    assert kwargs["coalesce"] is True

    scheduler.start.assert_called_once_with()
    assert service._scheduler == scheduler


def test_start_returns_early_when_scheduler_already_exists():
    app = build_app()
    existing_scheduler = Mock()

    with patch("app.services.scheduler_service.BackgroundScheduler") as mock_scheduler_cls, \
         patch("app.services.scheduler_service.IntervalTrigger") as mock_interval_trigger:

        service = SchedulerService(app=app, _scheduler=existing_scheduler)
        service.start()

    mock_scheduler_cls.assert_not_called()
    mock_interval_trigger.assert_not_called()
    assert service._scheduler is existing_scheduler


def test_added_job_function_calls_run_job_safely():
    app = build_app()

    with patch("app.services.scheduler_service.BackgroundScheduler") as mock_scheduler_cls, \
         patch("app.services.scheduler_service.IntervalTrigger"):

        scheduler = mock_scheduler_cls.return_value
        service = SchedulerService(app=app)

        with patch.object(service, "_run_job_safely") as mock_run_job_safely:
            service.start()

            job_func = scheduler.add_job.call_args.kwargs["func"]
            job_func()

    mock_run_job_safely.assert_called_once_with()


def test_run_job_safely_runs_job_service_inside_app_context():
    app = build_app()
    app_context = MagicMock()
    app.app_context.return_value = app_context

    with patch("app.services.scheduler_service.JobService") as mock_job_service:
        service = SchedulerService(app=app)
        service._run_job_safely()

    app.app_context.assert_called_once_with()
    app_context.__enter__.assert_called_once_with()
    app_context.__exit__.assert_called_once()
    mock_job_service.assert_called_once_with(app)
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(
        trigger=SCHEDULED_TRIGGER
    )


def test_run_job_safely_swallows_and_logs_exceptions():
    app = build_app()
    app_context = MagicMock()
    app.app_context.return_value = app_context

    with patch("app.services.scheduler_service.JobService") as mock_job_service, \
         patch("app.services.scheduler_service.log") as mock_log:

        mock_job_service.return_value.run_sync_and_export.side_effect = RuntimeError("boom")

        service = SchedulerService(app=app)
        service._run_job_safely()

    mock_job_service.assert_called_once_with(app)
    mock_job_service.return_value.run_sync_and_export.assert_called_once_with(
        trigger=SCHEDULED_TRIGGER
    )
    mock_log.exception.assert_called_once_with("Scheduled sync/export job failed.")