from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, CallLog, Restaurant
from app.schemas.owner import OwnerAgendaDay, OwnerAgendaResponse, OwnerAgendaSummary, OwnerAgendaTurno
from app.services.availability import COUNTABLE_STATUSES, parse_turni, restaurant_now

FOLLOW_UP_OUTCOMES = {"tool_error", "abandoned"}

WEEKDAY_LABELS = {
    0: "Lunedì",
    1: "Martedì",
    2: "Mercoledì",
    3: "Giovedì",
    4: "Venerdì",
    5: "Sabato",
    6: "Domenica",
}


def _fullness(occupancy_ratio: float) -> str:
    if occupancy_ratio > 1:
        return "overbooked-risk"
    if occupancy_ratio >= 0.85:
        return "full"
    if occupancy_ratio >= 0.45:
        return "healthy"
    return "low"


def _day_window_utc(day: date, timezone: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def owner_agenda(
    db: Session,
    *,
    restaurant: Restaurant,
    days: int = 7,
    start_day: date | None = None,
) -> OwnerAgendaResponse:
    resolved_start = start_day or restaurant_now(restaurant).date()
    resolved_end = resolved_start + timedelta(days=max(days - 1, 0))

    booking_rows = db.execute(
        select(
            Booking.date,
            Booking.turno,
            func.coalesce(func.sum(Booking.party_size), 0).label("booked_covers"),
            func.count(Booking.id).label("booking_count"),
        )
        .where(
            Booking.restaurant_id == restaurant.id,
            Booking.date >= resolved_start,
            Booking.date <= resolved_end,
            Booking.status.in_(COUNTABLE_STATUSES),
        )
        .group_by(Booking.date, Booking.turno)
    ).all()

    bookings_by_day_turno: dict[tuple[date, str], tuple[int, int]] = {
        (row.date, row.turno): (int(row.booked_covers or 0), int(row.booking_count or 0))
        for row in booking_rows
    }

    today_start_utc, today_end_utc = _day_window_utc(resolved_start, restaurant.timezone)
    calls_today = int(
        db.scalar(
            select(func.count(CallLog.id)).where(
                CallLog.restaurant_id == restaurant.id,
                CallLog.started_at >= today_start_utc,
                CallLog.started_at < today_end_utc,
            )
        )
        or 0
    )
    unresolved_today = int(
        db.scalar(
            select(func.count(CallLog.id)).where(
                CallLog.restaurant_id == restaurant.id,
                CallLog.started_at >= today_start_utc,
                CallLog.started_at < today_end_utc,
                (
                    (CallLog.call_status == "failed")
                    | (CallLog.outcome.in_(FOLLOW_UP_OUTCOMES))
                ),
            )
        )
        or 0
    )

    normalized_weekly_closures = {day_name.strip().lower() for day_name in restaurant.weekly_closures or []}
    closure_dates = set(restaurant.closure_dates or [])

    agenda_days: list[OwnerAgendaDay] = []
    today_booked_covers = 0

    for offset in range(days):
        current_day = resolved_start + timedelta(days=offset)
        is_today = current_day == resolved_start
        weekday_name = current_day.strftime("%A").lower()
        is_closed = current_day.isoformat() in closure_dates or weekday_name in normalized_weekly_closures

        if current_day.isoformat() in closure_dates:
            closure_label = "Chiusura straordinaria"
        elif weekday_name in normalized_weekly_closures:
            closure_label = "Chiuso di turno"
        else:
            closure_label = None

        turni_payload: list[OwnerAgendaTurno] = []
        total_booked_covers = 0
        total_booking_count = 0
        total_remaining_covers = 0

        for turno in parse_turni(restaurant):
            booked_covers, booking_count = bookings_by_day_turno.get((current_day, turno.name), (0, 0))
            remaining_covers = max(turno.max_covers - booked_covers, 0) if not is_closed else 0
            occupancy_ratio = round((booked_covers / turno.max_covers), 3) if turno.max_covers else 0

            total_booked_covers += booked_covers
            total_booking_count += booking_count
            total_remaining_covers += remaining_covers

            turni_payload.append(
                OwnerAgendaTurno(
                    turno=turno.name,
                    start=turno.start.strftime("%H:%M"),
                    end=turno.end.strftime("%H:%M"),
                    booked_covers=booked_covers,
                    booking_count=booking_count,
                    max_covers=turno.max_covers,
                    remaining_covers=remaining_covers,
                    occupancy_ratio=occupancy_ratio,
                    fullness=_fullness(occupancy_ratio),
                )
            )

        if is_today:
            today_booked_covers = total_booked_covers

        agenda_days.append(
            OwnerAgendaDay(
                date=current_day.isoformat(),
                weekday_label=WEEKDAY_LABELS[current_day.weekday()],
                is_today=is_today,
                is_closed=is_closed,
                closure_label=closure_label,
                total_booked_covers=total_booked_covers,
                total_booking_count=total_booking_count,
                total_remaining_covers=total_remaining_covers,
                turni=turni_payload,
            )
        )

    return OwnerAgendaResponse(
        restaurant_id=restaurant.id,
        timezone=restaurant.timezone,
        days=agenda_days,
        summary=OwnerAgendaSummary(
            today_booked_covers=today_booked_covers,
            today_calls=calls_today,
            today_unresolved_calls=unresolved_today,
        ),
    )
