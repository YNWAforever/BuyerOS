from buyeros_worker.app import celery_app, configure_eager
from buyeros_worker.config import WorkerSettings


def test_settings_defaults_are_safe():
    s = WorkerSettings()
    assert s.lease_seconds == 120
    assert s.batch_size == 10
    assert s.eager is False


def test_celery_app_is_named_and_has_no_result_backend():
    assert celery_app.main == "buyeros_worker"
    assert celery_app.conf.task_ignore_result is True


def test_eager_mode_can_be_enabled():
    configure_eager(celery_app, True)
    assert celery_app.conf.task_always_eager is True
    configure_eager(celery_app, False)
    assert celery_app.conf.task_always_eager is False
