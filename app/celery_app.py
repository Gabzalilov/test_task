from celery import Celery

from app.config import get_settings
from app.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

celery_app = Celery("booking_service", include=["app.tasks"])
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="bookings",
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)
