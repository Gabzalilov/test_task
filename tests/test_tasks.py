from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.models import Booking, BookingStatus
from app.tasks import handle_booking_processing, mark_booking_failed


def create_booking_record(db: Session, *, status: BookingStatus = BookingStatus.pending) -> Booking:
    booking = Booking(
        name="Anna",
        starts_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        service_type="consultation",
        status=status,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def test_worker_confirms_pending_booking_once(session_factory: sessionmaker[Session], db_session: Session, monkeypatch):
    booking = create_booking_record(db_session)
    sent_notifications: list[str] = []

    monkeypatch.setattr("app.tasks.SessionLocal", session_factory)

    result = handle_booking_processing(
        booking.id,
        should_fail=lambda: False,
        notify=lambda processed_booking: sent_notifications.append(processed_booking.id),
    )
    second_result = handle_booking_processing(
        booking.id,
        should_fail=lambda: False,
        notify=lambda processed_booking: sent_notifications.append(processed_booking.id),
    )

    db_session.expire_all()
    assert result == {"status": "confirmed"}
    assert second_result == {"status": "confirmed"}
    assert db_session.get(Booking, booking.id).status == BookingStatus.confirmed
    assert sent_notifications == [booking.id]


def test_worker_marks_pending_booking_failed(session_factory: sessionmaker[Session], db_session: Session, monkeypatch):
    booking = create_booking_record(db_session)

    monkeypatch.setattr("app.tasks.SessionLocal", session_factory)

    result = mark_booking_failed(booking.id, "external service temporarily unavailable")

    db_session.expire_all()
    persisted = db_session.get(Booking, booking.id)
    assert result == {"status": "failed"}
    assert persisted.status == BookingStatus.failed
    assert persisted.failure_reason == "external service temporarily unavailable"
