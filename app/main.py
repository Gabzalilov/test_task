import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.logging import configure_logging
from app.models import Booking, BookingStatus
from app.rate_limit import rate_limiter
from app.schemas import BookingCreate, BookingList, BookingRead
from app.tasks import process_booking

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Booking Service", version="1.0.0")


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def enforce_post_rate_limit(request: Request, settings: AppSettings) -> None:
    client_host = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_host, settings.post_bookings_rate_limit_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many booking requests",
        )


@app.post(
    "/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_post_rate_limit)],
)
def create_booking(payload: BookingCreate, db: DbSession) -> BookingRead:
    booking = Booking(
        name=payload.name,
        starts_at=payload.datetime,
        service_type=payload.service_type,
        status=BookingStatus.pending,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    process_booking.delay(booking.id)
    logger.info("booking_created", extra={"booking_id": booking.id, "status": booking.status.value})
    return BookingRead.from_model(booking)


@app.get("/bookings/{booking_id}", response_model=BookingRead)
def get_booking(booking_id: str, db: DbSession) -> BookingRead:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return BookingRead.from_model(booking)


@app.get("/bookings", response_model=BookingList)
def list_bookings(
    db: DbSession,
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BookingList:
    filters = []
    if booking_status is not None:
        filters.append(Booking.status == booking_status)

    count_statement = select(func.count()).select_from(Booking).where(*filters)
    total = db.execute(count_statement).scalar_one()

    statement = (
        select(Booking)
        .where(*filters)
        .order_by(Booking.created_at.desc(), Booking.id.desc())
        .limit(limit)
        .offset(offset)
    )
    bookings = db.execute(statement).scalars().all()

    return BookingList(
        items=[BookingRead.from_model(booking) for booking in bookings],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: str, db: DbSession) -> Response:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != BookingStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending bookings can be cancelled",
        )

    db.delete(booking)
    db.commit()
    logger.info("booking_cancelled", extra={"booking_id": booking_id, "status": BookingStatus.pending.value})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
