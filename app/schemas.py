from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Booking, BookingStatus


class BookingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    datetime: datetime
    service_type: str = Field(min_length=1, max_length=100)


class BookingRead(BaseModel):
    id: str
    name: str
    datetime: datetime
    service_type: str
    status: BookingStatus
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, booking: Booking) -> "BookingRead":
        return cls(
            id=booking.id,
            name=booking.name,
            datetime=booking.starts_at,
            service_type=booking.service_type,
            status=booking.status,
            failure_reason=booking.failure_reason,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )


class BookingList(BaseModel):
    items: list[BookingRead]
    total: int
    limit: int
    offset: int
