from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus


def booking_payload(**overrides):
    payload = {
        "name": "Anna",
        "datetime": "2026-07-01T10:00:00Z",
        "service_type": "consultation",
    }
    payload.update(overrides)
    return payload


def create_booking_record(db: Session, *, status: BookingStatus = BookingStatus.pending, name: str = "Anna") -> Booking:
    booking = Booking(
        name=name,
        starts_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        service_type="consultation",
        status=status,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def test_create_booking_returns_pending_and_enqueues_task(client, enqueued_booking_ids):
    response = client.post("/bookings", json=booking_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["name"] == "Anna"
    assert enqueued_booking_ids == [body["id"]]


def test_create_booking_validates_payload(client):
    response = client.post("/bookings", json=booking_payload(name=""))

    assert response.status_code == 422


def test_get_booking_returns_status(client, db_session):
    booking = create_booking_record(db_session, status=BookingStatus.confirmed)

    response = client.get(f"/bookings/{booking.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_list_bookings_filters_by_status_and_paginates(client, db_session):
    create_booking_record(db_session, status=BookingStatus.pending, name="Pending")
    confirmed_one = create_booking_record(db_session, status=BookingStatus.confirmed, name="Confirmed one")
    confirmed_two = create_booking_record(db_session, status=BookingStatus.confirmed, name="Confirmed two")

    response = client.get("/bookings", params={"status": "confirmed", "limit": 1, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] in {confirmed_one.id, confirmed_two.id}


def test_list_bookings_rejects_unknown_status(client):
    response = client.get("/bookings", params={"status": "cancelled"})

    assert response.status_code == 422


def test_delete_pending_booking_cancels_it(client, db_session):
    booking = create_booking_record(db_session, status=BookingStatus.pending)

    delete_response = client.delete(f"/bookings/{booking.id}")
    get_response = client.get(f"/bookings/{booking.id}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_confirmed_booking_is_rejected(client, db_session):
    booking = create_booking_record(db_session, status=BookingStatus.confirmed)

    response = client.delete(f"/bookings/{booking.id}")

    assert response.status_code == 409
