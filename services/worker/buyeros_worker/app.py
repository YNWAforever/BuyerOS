from celery import Celery

from .config import get_settings


def configure_eager(app: Celery, enabled: bool) -> None:
    app.conf.task_always_eager = bool(enabled)


def build_app() -> Celery:
    settings = get_settings()
    app = Celery("buyeros_worker", broker=settings.broker_url)
    app.conf.update(
        task_ignore_result=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        beat_schedule={
            "buyeros-sweep-expired": {
                "task": "buyeros.sweep",
                "schedule": float(settings.sweep_seconds),
            }
        },
    )
    configure_eager(app, settings.eager)
    return app


celery_app = build_app()

celery_app.autodiscover_tasks(["buyeros_worker"])
