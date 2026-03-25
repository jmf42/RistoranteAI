from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRole(StrEnum):
    operator = "operator"
    owner = "owner"


class BookingStatus(StrEnum):
    confirmed = "confirmed"
    modified = "modified"
    cancelled = "cancelled"
    no_show = "no_show"
    completed = "completed"


class BookingSource(StrEnum):
    ai_phone = "ai_phone"
    dashboard = "dashboard"
    walk_in = "walk_in"


class CallOutcome(StrEnum):
    booking_created = "booking_created"
    booking_modified = "booking_modified"
    booking_cancelled = "booking_cancelled"
    info_provided = "info_provided"
    escalated = "escalated"
    abandoned = "abandoned"


class SyncStatus(AppBaseModel):
    synced: bool
    message: str
