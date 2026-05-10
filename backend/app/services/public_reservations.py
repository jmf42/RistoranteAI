from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Booking, BookingGuestToken, Restaurant

ONLINE_BOOKING_DEFAULTS = {
    "enabled": True,
    "default_locale": "it-IT",
    "modify_cutoff_hours": 6,
    "cancel_cutoff_hours": 6,
    "require_email": True,
    "party_size_min": 1,
    "party_size_max": 8,
    "confirmation_message": "Prenotazione confermata. Riceverai un link per gestirla online.",
    "public_page_enabled": True,
    "widget_enabled": False,
}


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def resolved_online_booking_settings(restaurant: Restaurant) -> dict[str, object]:
    return {**ONLINE_BOOKING_DEFAULTS, **(restaurant.online_booking_settings or {})}


def get_public_restaurant_or_404(db: Session, slug: str) -> Restaurant:
    restaurant = db.scalar(
        select(Restaurant).where(Restaurant.slug == slug, Restaurant.is_active.is_(True))
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    config = resolved_online_booking_settings(restaurant)
    if not config["enabled"] or not config["public_page_enabled"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online reservations unavailable")
    return restaurant


def effective_public_party_size_max(restaurant: Restaurant) -> int:
    booking_rules = restaurant.booking_rules or {}
    online_settings = resolved_online_booking_settings(restaurant)
    limits = [
        int(booking_rules.get("max_party", 20)),
        int(booking_rules.get("large_group_threshold", 8)),
        int(online_settings["party_size_max"]),
    ]
    return min(limits)


def enforce_public_booking_rules(restaurant: Restaurant, *, party_size: int) -> None:
    online_settings = resolved_online_booking_settings(restaurant)
    min_party = int(online_settings["party_size_min"])
    max_party = effective_public_party_size_max(restaurant)
    if party_size < min_party:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Online bookings start at {min_party} guests.",
        )
    if party_size > max_party:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Online bookings are limited to {max_party} guests for this restaurant.",
        )


def _hash_manage_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_manage_token(db: Session, *, booking: Booking, expires_in_days: int = 30) -> str:
    raw_token = secrets.token_urlsafe(24)
    token = BookingGuestToken(
        booking_id=booking.id,
        purpose="manage",
        access_version=booking.guest_access_version,
        token_hash=_hash_manage_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
    )
    db.add(token)
    db.flush()
    return raw_token


def booking_from_manage_token(db: Session, raw_token: str) -> tuple[BookingGuestToken, Booking]:
    token = db.scalar(
        select(BookingGuestToken).where(
            BookingGuestToken.token_hash == _hash_manage_token(raw_token),
            BookingGuestToken.purpose == "manage",
        )
    )
    if not token or token.revoked_at is not None or _as_utc(token.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking link not found")
    booking = db.get(Booking, token.booking_id)
    if not booking or token.access_version != booking.guest_access_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking link not found")
    token.last_used_at = datetime.now(UTC)
    db.add(token)
    db.flush()
    return token, booking


def manage_url_for_token(raw_token: str, request_base_url: str | None = None) -> str:
    base_url = (
        settings.public_web_base_url
        or request_base_url
        or (settings.allowed_origins[0] if settings.allowed_origins else "")
    ).rstrip("/")
    path = f"/reserve/manage/{raw_token}"
    if not base_url:
        return path
    return urljoin(f"{base_url}/", path.lstrip("/"))


def cutoff_allows_action(*, booking: Booking, restaurant: Restaurant, hours_before: int) -> bool:
    timezone = ZoneInfo(restaurant.timezone)
    now = datetime.now(UTC).astimezone(timezone)
    booking_dt = datetime.combine(booking.date, booking.time, tzinfo=timezone)
    return booking.status in {"confirmed", "modified"} and (booking_dt - now) >= timedelta(hours=hours_before)
