from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, Restaurant

ACTIVE_STATUSES = {"confirmed", "modified"}
COUNTABLE_STATUSES = {"confirmed", "modified", "completed"}


@dataclass
class Turno:
    name: str
    start: time
    end: time
    max_covers: int


def parse_turni(restaurant: Restaurant) -> list[Turno]:
    turni: list[Turno] = []
    for item in restaurant.turni:
        turni.append(
            Turno(
                name=item["name"],
                start=time.fromisoformat(item["start"]),
                end=time.fromisoformat(item["end"]),
                max_covers=int(item["max_covers"]),
            )
        )
    return sorted(turni, key=lambda item: item.start)


def booking_rules(restaurant: Restaurant) -> dict[str, int]:
    defaults = {
        "min_party": 1,
        "max_party": 20,
        "large_group_threshold": 8,
        "max_advance_days": 60,
        "min_lead_hours": 2,
    }
    return {**defaults, **(restaurant.booking_rules or {})}


def restaurant_now(restaurant: Restaurant, now: datetime | None = None) -> datetime:
    if now is not None:
        return now.astimezone(ZoneInfo(restaurant.timezone))
    return datetime.now(UTC).astimezone(ZoneInfo(restaurant.timezone))


def resolve_turno(turni: list[Turno], requested_time: time | None) -> Turno | None:
    if requested_time is None:
        return turni[0] if turni else None
    for turno in turni:
        if turno.start <= requested_time < turno.end:
            return turno
    return None


def representative_time(turno: Turno, requested_time: time | None) -> str:
    if requested_time and turno.start <= requested_time < turno.end:
        return requested_time.strftime("%H:%M")
    return turno.start.strftime("%H:%M")


def turno_remaining_covers(
    db: Session,
    *,
    restaurant_id: str,
    booking_date: date,
    turno_name: str,
    max_covers: int,
    exclude_booking_id: str | None = None,
) -> int:
    stmt = select(func.coalesce(func.sum(Booking.party_size), 0)).where(
        Booking.restaurant_id == restaurant_id,
        Booking.date == booking_date,
        Booking.turno == turno_name,
        Booking.status.in_(ACTIVE_STATUSES),
    )
    if exclude_booking_id:
        stmt = stmt.where(Booking.id != exclude_booking_id)
    booked = db.scalar(stmt) or 0
    return max(max_covers - int(booked), 0)


def validate_open_rules(
    restaurant: Restaurant,
    *,
    booking_date: date,
    requested_time: time | None,
    party_size: int,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    rules = booking_rules(restaurant)
    local_now = restaurant_now(restaurant, now)
    if party_size < int(rules["min_party"]):
        return False, f"La prenotazione minima è per {rules['min_party']} persone."
    if party_size > int(rules["max_party"]):
        return False, f"Accettiamo prenotazioni online fino a {rules['max_party']} persone."
    if booking_date.isoformat() in (restaurant.closure_dates or []):
        return False, "Il ristorante è chiuso in quella data."
    weekday = booking_date.strftime("%A").lower()
    if weekday in {day.lower() for day in restaurant.weekly_closures or []}:
        return False, f"Il ristorante è chiuso il {weekday}."
    if booking_date > (local_now.date() + timedelta(days=int(rules["max_advance_days"]))):
        return False, (
            f"Le prenotazioni sono disponibili fino a {rules['max_advance_days']} giorni in anticipo."
        )
    if requested_time and booking_date == local_now.date():
        requested_dt = datetime.combine(booking_date, requested_time, tzinfo=ZoneInfo(restaurant.timezone))
        min_allowed = local_now + timedelta(hours=int(rules["min_lead_hours"]))
        if requested_dt < min_allowed:
            return (
                False,
                f"Per prenotazioni in giornata serve almeno {rules['min_lead_hours']} ore di anticipo.",
            )
    return True, None


def check_availability(
    db: Session,
    *,
    restaurant: Restaurant,
    booking_date: date,
    requested_time: time | None,
    party_size: int,
    exclude_booking_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    is_open, reason = validate_open_rules(
        restaurant,
        booking_date=booking_date,
        requested_time=requested_time,
        party_size=party_size,
        now=now,
    )
    if not is_open:
        return {"open": False, "available": False, "reason": reason, "alternatives": []}

    turni = parse_turni(restaurant)
    selected_turno = resolve_turno(turni, requested_time)
    if not selected_turno:
        alternatives = []
        for turno in turni:
            remaining = turno_remaining_covers(
                db,
                restaurant_id=restaurant.id,
                booking_date=booking_date,
                turno_name=turno.name,
                max_covers=turno.max_covers,
                exclude_booking_id=exclude_booking_id,
            )
            if remaining >= party_size:
                alternatives.append(
                    {
                        "time": turno.start.strftime("%H:%M"),
                        "turno": turno.name,
                        "remaining": remaining,
                    }
                )
        return {
            "open": True,
            "available": False,
            "reason": "L'orario richiesto è fuori servizio.",
            "alternatives": alternatives[:2],
        }

    remaining = turno_remaining_covers(
        db,
        restaurant_id=restaurant.id,
        booking_date=booking_date,
        turno_name=selected_turno.name,
        max_covers=selected_turno.max_covers,
        exclude_booking_id=exclude_booking_id,
    )
    if remaining >= party_size:
        return {
            "open": True,
            "available": True,
            "slot": {
                "time": representative_time(selected_turno, requested_time),
                "turno": selected_turno.name,
                "remaining": remaining - party_size,
            },
            "alternatives": [],
        }

    alternatives = []
    for turno in turni:
        if turno.name == selected_turno.name:
            continue
        turno_remaining = turno_remaining_covers(
            db,
            restaurant_id=restaurant.id,
            booking_date=booking_date,
            turno_name=turno.name,
            max_covers=turno.max_covers,
            exclude_booking_id=exclude_booking_id,
        )
        if turno_remaining >= party_size:
            alternatives.append(
                {
                    "time": representative_time(turno, requested_time),
                    "turno": turno.name,
                    "remaining": turno_remaining - party_size,
                }
            )
    return {"open": True, "available": False, "alternatives": alternatives[:2]}


def capacity_snapshot(db: Session, *, restaurant: Restaurant, booking_date: date) -> list[dict[str, Any]]:
    slots = []
    for turno in parse_turni(restaurant):
        remaining = turno_remaining_covers(
            db,
            restaurant_id=restaurant.id,
            booking_date=booking_date,
            turno_name=turno.name,
            max_covers=turno.max_covers,
        )
        booked = turno.max_covers - remaining
        slots.append(
            {
                "turno": turno.name,
                "start": turno.start.strftime("%H:%M"),
                "end": turno.end.strftime("%H:%M"),
                "booked_covers": booked,
                "max_covers": turno.max_covers,
                "remaining_covers": remaining,
                "occupancy_ratio": round(booked / turno.max_covers, 3) if turno.max_covers else 0,
            }
        )
    return slots
