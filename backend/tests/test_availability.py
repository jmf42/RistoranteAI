from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models import Restaurant
from app.services.availability import check_availability


def _next_open_day() -> date:
    candidate = date.today() + timedelta(days=1)
    while candidate.strftime("%A").lower() == "monday":
        candidate += timedelta(days=1)
    return candidate


def test_closed_weekday_returns_open_false(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    next_monday = date.today()
    while next_monday.strftime("%A").lower() != "monday":
        next_monday += timedelta(days=1)
    result = check_availability(
        db_session,
        restaurant=restaurant,
        booking_date=next_monday,
        requested_time=None,
        party_size=2,
    )
    assert result["open"] is False
    assert "chiuso" in result["reason"].lower()


def test_available_turno_returns_slot(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    result = check_availability(
        db_session,
        restaurant=restaurant,
        booking_date=_next_open_day(),
        requested_time=None,
        party_size=2,
    )
    assert result["open"] is True
    assert result["available"] is True
    assert result["slot"]["turno"] in {"primo", "secondo"}
