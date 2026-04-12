from __future__ import annotations

from app.schemas.common import AppBaseModel


class OwnerAgendaSummary(AppBaseModel):
    today_booked_covers: int
    today_calls: int
    today_unresolved_calls: int


class OwnerAgendaTurno(AppBaseModel):
    turno: str
    start: str
    end: str
    booked_covers: int
    booking_count: int
    max_covers: int
    remaining_covers: int
    occupancy_ratio: float
    fullness: str


class OwnerAgendaDay(AppBaseModel):
    date: str
    weekday_label: str
    is_today: bool
    is_closed: bool
    closure_label: str | None = None
    total_booked_covers: int
    total_booking_count: int
    total_remaining_covers: int
    turni: list[OwnerAgendaTurno]


class OwnerAgendaResponse(AppBaseModel):
    restaurant_id: str
    timezone: str
    days: list[OwnerAgendaDay]
    summary: OwnerAgendaSummary
