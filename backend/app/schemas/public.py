from __future__ import annotations

from datetime import date as DateValue
from datetime import time as TimeValue

from pydantic import EmailStr, Field

from app.schemas.booking import BookingRead
from app.schemas.common import AppBaseModel
from app.schemas.tools import CheckAvailabilityResponse


class PublicRestaurantSummary(AppBaseModel):
    name: str
    slug: str
    timezone: str
    address: str


class OnlineBookingSettingsRead(AppBaseModel):
    enabled: bool
    default_locale: str
    modify_cutoff_hours: int
    cancel_cutoff_hours: int
    require_email: bool
    party_size_min: int
    party_size_max: int
    confirmation_message: str
    public_page_enabled: bool
    widget_enabled: bool


class PublicReservationConfigResponse(AppBaseModel):
    restaurant: PublicRestaurantSummary
    online_booking: OnlineBookingSettingsRead
    turni: list[dict[str, object]]


class PublicAvailabilityRequest(AppBaseModel):
    date: DateValue
    time: TimeValue | None = None
    party_size: int = Field(ge=1, le=30)


class PublicBookingCreateRequest(AppBaseModel):
    date: DateValue
    time: TimeValue
    party_size: int = Field(ge=1, le=30)
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=6, max_length=30)
    customer_email: EmailStr | None = None
    special_requests: str | None = Field(default=None, max_length=2000)


class PublicBookingModifyRequest(AppBaseModel):
    date: DateValue | None = None
    time: TimeValue | None = None
    party_size: int | None = Field(default=None, ge=1, le=30)
    special_requests: str | None = Field(default=None, max_length=2000)


class PublicBookingReadResponse(AppBaseModel):
    booking: BookingRead
    can_modify: bool
    can_cancel: bool


class PublicBookingCreateResponse(AppBaseModel):
    booking: BookingRead
    manage_url: str
    notification_status: str


class PublicAvailabilityResponse(AppBaseModel):
    restaurant_slug: str
    result: CheckAvailabilityResponse
