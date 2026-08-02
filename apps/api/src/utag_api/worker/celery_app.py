from celery import Celery

from utag_api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "utag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["utag_api.worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Accra",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "relay-outbox-every-second": {
            "task": "utag.outbox.relay",
            "schedule": 1.0,
        },
        "expire-sessions-hourly": {
            "task": "utag.sessions.expire",
            "schedule": 3600.0,
        },
        "publish-scheduled-content-every-minute": {
            "task": "utag.content.publish_scheduled",
            "schedule": 60.0,
        },
    },
    task_routes={
        "utag.media.*": {"queue": "media"},
        "utag.imports.*": {"queue": "imports"},
        "utag.email.*": {"queue": "communications"},
    },
)
