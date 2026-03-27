from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db, get_restaurant_or_404, require_roles
from app.integrations.elevenlabs import elevenlabs_service
from app.models import Booking, CallLog, Restaurant, User
from app.schemas.common import SyncStatus
from app.schemas.restaurant import RestaurantCreate, RestaurantRead, RestaurantSummary, RestaurantUpdate
from app.services.availability import COUNTABLE_STATUSES

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def _assistant_settings_payload(restaurant: Restaurant) -> dict:
    settings = dict(getattr(restaurant, "assistant_settings", {}) or {})
    settings.setdefault("llm_provider", "openai")
    settings.setdefault("openai_model", "gpt-5-mini")
    settings.setdefault("reasoning_effort", "minimal")
    settings.setdefault("response_verbosity", "low")
    settings.setdefault("custom_greeting", None)
    settings.setdefault("agent_style_notes", "Warm, concise, premium Italian hospitality tone.")
    return settings


def _apply_restaurant_payload(restaurant: Restaurant, payload: RestaurantCreate | RestaurantUpdate) -> None:
    data = payload.model_dump(exclude_none=True)
    assistant_settings = _assistant_settings_payload(restaurant)
    custom_greeting = data.pop("custom_greeting", None) if "custom_greeting" in data else None
    agent_style_notes = data.pop("agent_style_notes", None) if "agent_style_notes" in data else None

    for field, value in data.items():
        setattr(restaurant, field, value)

    if "custom_greeting" in payload.model_fields_set:
        assistant_settings["custom_greeting"] = custom_greeting
    if "agent_style_notes" in payload.model_fields_set:
        assistant_settings["agent_style_notes"] = agent_style_notes
    restaurant.assistant_settings = assistant_settings


def _raise_restaurant_integrity_error(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc)).lower()
    if "slug" in message:
        detail = "Restaurant slug already exists"
    else:
        detail = "Restaurant data conflicts with an existing record"
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def _to_read(restaurant: Restaurant, sync_status: SyncStatus | None = None) -> RestaurantRead:
    assistant_settings = _assistant_settings_payload(restaurant)
    return RestaurantRead(
        id=restaurant.id,
        slug=restaurant.slug,
        name=restaurant.name,
        twilio_phone=restaurant.twilio_phone,
        elevenlabs_agent_id=restaurant.elevenlabs_agent_id,
        timezone=restaurant.timezone,
        address=restaurant.address,
        opening_hours=restaurant.opening_hours,
        weekly_closures=restaurant.weekly_closures,
        closure_dates=restaurant.closure_dates,
        turni=restaurant.turni,
        booking_rules=restaurant.booking_rules,
        custom_greeting=assistant_settings.get("custom_greeting"),
        agent_style_notes=assistant_settings.get("agent_style_notes"),
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
    restaurant = Restaurant()
    _apply_restaurant_payload(restaurant, payload)
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_restaurant_integrity_error(exc)
    db.refresh(restaurant)
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
    _apply_restaurant_payload(restaurant, payload)
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _raise_restaurant_integrity_error(exc)
    db.refresh(restaurant)
    sync_status = None
    if sync_agent:
        sync_result = elevenlabs_service.sync_restaurant_config(restaurant)
        sync_status = SyncStatus(synced=sync_result.synced, message=sync_result.message)
    return _to_read(restaurant, sync_status=sync_status)
