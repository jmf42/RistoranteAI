from __future__ import annotations

from datetime import date as DateValue
from datetime import time as TimeValue
from typing import Any

from pydantic import Field

from app.schemas.common import AppBaseModel


class SlotOption(AppBaseModel):
    time: str
    turno: str
    remaining: int | None = None


class CheckAvailabilityRequest(AppBaseModel):
    restaurant_id: str
    date: DateValue
    time_preference: TimeValue | None = None
    party_size: int = Field(ge=1, le=30)


class CheckAvailabilityResponse(AppBaseModel):
    open: bool
    available: bool = False
    reason: str | None = None
    slot: SlotOption | None = None
    alternatives: list[SlotOption] = Field(default_factory=list)


class CreateBookingToolRequest(AppBaseModel):
    restaurant_id: str
    date: DateValue
    time: TimeValue
    party_size: int = Field(ge=1, le=30)
    customer_name: str = Field(min_length=2)
    customer_phone: str
    special_requests: str | None = None
    caller_phone: str | None = None


class CreateBookingToolResponse(AppBaseModel):
    success: bool
    confirmation_code: str | None = None
    reason: str | None = None
    alternatives: list[SlotOption] = Field(default_factory=list)


class FindBookingRequest(AppBaseModel):
    restaurant_id: str
    caller_phone: str | None = None
    confirmation_code: str | None = None


class FindBookingResponse(AppBaseModel):
    found: bool
    bookings: list[dict[str, Any]] = Field(default_factory=list)


class ModifyBookingChanges(AppBaseModel):
    date: DateValue | None = None
    time: TimeValue | None = None
    party_size: int | None = Field(default=None, ge=1, le=30)
    customer_name: str | None = None
    customer_phone: str | None = None
    special_requests: str | None = None


class ModifyBookingRequest(AppBaseModel):
    restaurant_id: str | None = None
    confirmation_code: str
    changes: ModifyBookingChanges


class ModifyBookingResponse(AppBaseModel):
    success: bool
    reason: str | None = None
    updated_booking: dict[str, Any] | None = None
    alternatives: list[SlotOption] = Field(default_factory=list)


class CancelBookingRequest(AppBaseModel):
    restaurant_id: str | None = None
    confirmation_code: str


class CancelBookingResponse(AppBaseModel):
    success: bool


class TwilioPersonalizationRequest(AppBaseModel):
    caller_id: str
    agent_id: str
    called_number: str
    call_sid: str


class TwilioPersonalizationResponse(AppBaseModel):
    type: str = "conversation_initiation_client_data"
    dynamic_variables: dict[str, Any]
