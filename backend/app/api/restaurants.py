from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    accessible_restaurant_id,
    get_current_user,
    get_db,
    get_restaurant_or_404,
    invalidate_restaurant_cache,
    require_roles,
)
from app.models import Booking, CallLog, Restaurant, User
from app.schemas.common import SyncStatus
from app.schemas.restaurant import RestaurantCreate, RestaurantRead, RestaurantSummary, RestaurantUpdate
from app.services.availability import COUNTABLE_STATUSES, parse_turni

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def _check_turni_coverage(restaurant: Restaurant) -> list[str]:
    """Return warnings for opening_hours periods not covered by any turno."""
    warnings: list[str] = []
    turni = parse_turni(restaurant)
    if not turni:
        return warnings
    from datetime import time as Time

    for period, hours_str in (restaurant.opening_hours or {}).items():
        try:
            start_str, end_str = hours_str.split("-")
            period_start = Time.fromisoformat(start_str.strip())
            period_end = Time.fromisoformat(end_str.strip())
        except (ValueError, AttributeError):
            continue
        covered = any(
            turno.start <= period_start and turno.end >= period_end
            for turno in turni
        )
        if not covered:
            # Check if at least one turno overlaps this period
            partial = any(
                turno.start < period_end and turno.end > period_start
                for turno in turni
            )
            if not partial:
                warnings.append(
                    f"L'orario '{period}' ({hours_str}) non è coperto da nessun turno. "
                    f"Le prenotazioni in quella fascia verranno rifiutate."
                )
    return warnings


def _raise_restaurant_integrity_error(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc)).lower()
    if "slug" in message:
        detail = "Restaurant slug already exists"
    else:
        detail = "Restaurant data conflicts with an existing record"
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def _to_read(restaurant: Restaurant, sync_status: SyncStatus | None = None) -> RestaurantRead:
    return RestaurantRead(
        id=restaurant.id,
        slug=restaurant.slug,
        name=restaurant.name,
        twilio_phone=restaurant.twilio_phone,
        voice_provider=restaurant.voice_provider,
        timezone=restaurant.timezone,
        address=restaurant.address,
        opening_hours=restaurant.opening_hours,
        weekly_closures=restaurant.weekly_closures,
        closure_dates=restaurant.closure_dates,
        turni=restaurant.turni,
        booking_rules=restaurant.booking_rules,
        custom_greeting=restaurant.custom_greeting,
        agent_style_notes=restaurant.agent_style_notes,
        escalation_phone=restaurant.escalation_phone,
        is_active=restaurant.is_active,
        created_at=restaurant.created_at.isoformat(),
        updated_at=restaurant.updated_at.isoformat(),
        sync_status=sync_status,
    )


@router.get("/current", response_model=RestaurantRead)
def current_restaurant(
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RestaurantRead:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    restaurant = get_restaurant_or_404(db, resolved_id)
    return _to_read(restaurant)


@router.get("", response_model=list[RestaurantSummary], dependencies=[Depends(require_roles("operator"))])
def list_restaurants(db: Session = Depends(get_db)) -> list[RestaurantSummary]:
    restaurants = db.scalars(select(Restaurant).order_by(Restaurant.name.asc())).all()
    today = datetime.now(UTC).date()
    summaries: list[RestaurantSummary] = []
    for restaurant in restaurants:
        calls_today = int(
            db.scalar(
                select(func.count(CallLog.id)).where(
                    CallLog.restaurant_id == restaurant.id,
                    func.date(CallLog.started_at) == today,
                )
            )
            or 0
        )
        bookings_today = int(
            db.scalar(
                select(func.count(Booking.id)).where(
                    Booking.restaurant_id == restaurant.id,
                    Booking.date == today,
                    Booking.status.in_(COUNTABLE_STATUSES),
                )
            )
            or 0
        )
        booking_rate = round((bookings_today / calls_today) * 100, 2) if calls_today else 0
        summaries.append(
            RestaurantSummary(
                id=restaurant.id,
                slug=restaurant.slug,
                name=restaurant.name,
                twilio_phone=restaurant.twilio_phone,
                is_active=restaurant.is_active,
                calls_today=calls_today,
                bookings_today=bookings_today,
                booking_rate=booking_rate,
            )
        )
    return summaries


@router.post("", response_model=RestaurantRead, dependencies=[Depends(require_roles("operator"))])
def create_restaurant(payload: RestaurantCreate, db: Session = Depends(get_db)) -> RestaurantRead:
    restaurant = Restaurant(**payload.model_dump())
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_restaurant_integrity_error(exc)
    db.refresh(restaurant)
    invalidate_restaurant_cache(restaurant.id)
    return _to_read(restaurant)


@router.patch("/{restaurant_id}", response_model=RestaurantRead)
def update_restaurant(
    restaurant_id: str,
    payload: RestaurantUpdate,
    sync_agent: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RestaurantRead:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    restaurant = get_restaurant_or_404(db, resolved_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_restaurant_integrity_error(exc)
    db.refresh(restaurant)
    invalidate_restaurant_cache(restaurant.id)
    warnings = _check_turni_coverage(restaurant)
    sync_status = None
    if sync_agent:
        message = "Configurazione OpenAI aggiornata localmente."
        if warnings:
            message = f"{message} ⚠ {' '.join(warnings)}"
        sync_status = SyncStatus(synced=True, message=message)
    elif warnings:
        sync_status = SyncStatus(synced=True, message=f"⚠ {' '.join(warnings)}")
    return _to_read(restaurant, sync_status=sync_status)
