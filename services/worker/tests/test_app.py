from buyeros_worker.app import build_app, celery_app, configure_eager
from buyeros_worker.config import WorkerSettings


def test_settings_defaults_are_safe():
    s = WorkerSettings()
    assert s.lease_seconds == 120
    assert s.batch_size == 10
    assert s.eager is False
    assert s.sweep_seconds == 60


def test_celery_app_is_named_and_has_no_result_backend():
    assert celery_app.main == "buyeros_worker"
    assert celery_app.conf.task_ignore_result is True


def test_eager_mode_can_be_enabled():
    configure_eager(celery_app, True)
    assert celery_app.conf.task_always_eager is True
    configure_eager(celery_app, False)
    assert celery_app.conf.task_always_eager is False


def test_build_app_applies_eager_setting_and_beat_schedule(monkeypatch):
    monkeypatch.setattr("buyeros_worker.app.get_settings", lambda: WorkerSettings(eager=True, sweep_seconds=15))
    app = build_app()
    assert app.conf.task_always_eager is True
    schedule = app.conf.beat_schedule["buyeros-sweep-expired"]
    assert schedule["task"] == "buyeros.sweep"
    assert schedule["schedule"] == 15.0
