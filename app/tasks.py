import logging
import random
from typing import Callable

from sqlalchemy import select

from app.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.models import Booking, BookingStatus

logger = logging.getLogger(__name__)


class ExternalNotificationError(RuntimeError):
    pass


def send_mock_notification(booking: Booking) -> None:
    logger.info(
        "mock_notification_sent",
        extra={
            "booking_id": booking.id,
            "status": booking.status.value,
            "service_type": booking.service_type,
        },
    )


def _load_booking_for_update(db, booking_id: str) -> Booking | None:
    statement = select(Booking).where(Booking.id == booking_id)
    if db.bind and db.bind.dialect.name != "sqlite":
        statement = statement.with_for_update()
    return db.execute(statement).scalar_one_or_none()


def handle_booking_processing(
    booking_id: str,
    *,
    should_fail: Callable[[], bool] | None = None,
    notify: Callable[[Booking], None] = send_mock_notification,
) -> dict[str, str]:
    should_fail = should_fail or (lambda: random.random() < get_settings().booking_failure_rate)

    with SessionLocal() as db:
        booking = _load_booking_for_update(db, booking_id)
        if booking is None:
            logger.info("booking_not_found", extra={"booking_id": booking_id})
            return {"status": "not_found"}

        if booking.status != BookingStatus.pending:
            logger.info(
                "booking_already_processed",
                extra={"booking_id": booking.id, "status": booking.status.value},
            )
            return {"status": booking.status.value}

        if should_fail():
            raise ExternalNotificationError("external service temporarily unavailable")

        booking.status = BookingStatus.confirmed
        booking.failure_reason = None
        db.commit()
        db.refresh(booking)
        notify(booking)
        return {"status": BookingStatus.confirmed.value}


def mark_booking_failed(booking_id: str, reason: str) -> dict[str, str]:
    with SessionLocal() as db:
        booking = _load_booking_for_update(db, booking_id)
        if booking is None:
            logger.info("booking_not_found", extra={"booking_id": booking_id})
            return {"status": "not_found"}

        if booking.status != BookingStatus.pending:
            logger.info(
                "booking_failure_skipped",
                extra={"booking_id": booking.id, "status": booking.status.value},
            )
            return {"status": booking.status.value}

        booking.status = BookingStatus.failed
        booking.failure_reason = reason[:255]
        db.commit()
        logger.warning("booking_failed", extra={"booking_id": booking.id, "status": booking.status.value})
        return {"status": BookingStatus.failed.value}


@celery_app.task(bind=True, max_retries=3, name="app.tasks.process_booking")
def process_booking(self, booking_id: str) -> dict[str, str]:
    try:
        return handle_booking_processing(booking_id)
    except ExternalNotificationError as exc:
        retries = getattr(self.request, "retries", 0)
        if retries < self.max_retries:
            countdown = min(2**retries, 60)
            logger.warning(
                "booking_processing_retry",
                extra={"booking_id": booking_id, "status": BookingStatus.pending.value},
            )
            raise self.retry(exc=exc, countdown=countdown)
        return mark_booking_failed(booking_id, str(exc))
