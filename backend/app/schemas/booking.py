from __future__ import annotations

from datetime import date as DateValue
from datetime import time as TimeValue

from pydantic import Field

from app.schemas.common import AppBaseModel, BookingSource, BookingStatus


class BookingCreate(AppBaseModel):
    restaurant_id: str
    date: DateValue
    time: TimeValue
    party_size: int = Field(ge=1, le=30)
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=6, max_length=30)
    special_requests: str | None = Field(default=None, max_length=2000)
    source: BookingSource = BookingSource.dashboard
    status: BookingStatus = BookingStatus.confirmed


class BookingUpdate(AppBaseModel):
    date: DateValue | None = None
    time: TimeValue | None = None
    party_size: int | None = Field(default=None, ge=1, le=30)
    customer_name: str | None = Field(default=None, min_length=2, max_length=120)
    customer_phone: str | None = Field(default=None, min_length=6, max_length=30)
    special_requests: str | None = Field(default=None, max_length=2000)
    status: BookingStatus | None = None


class BookingRead(AppBaseModel):
    id: str
    restaurant_id: str
    confirmation_code: str
    date: DateValue
    time: TimeValue
    turno: str
    party_size: int
    customer_name: str
    customer_phone: str
    special_requests: str | None = Field(default=None, max_length=2000)
    status: BookingStatus
    source: BookingSource
    customer_id: str | None = None
    created_at: str
    updated_at: str


class BookingEventRead(AppBaseModel):
    id: str
    booking_id: str
    event_type: str
    changed_by: str | None = None
    changes: dict
    created_at: str
