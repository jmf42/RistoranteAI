from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_personalization_secret
from app.models import Restaurant
from app.schemas.tools import TwilioPersonalizationRequest, TwilioPersonalizationResponse

router = APIRouter(
    prefix="/integrations/elevenlabs",
    tags=["integrations"],
    dependencies=[Depends(verify_personalization_secret)],
)


def _greeting_for_restaurant(restaurant: Restaurant) -> str:
    local_now = datetime.now(ZoneInfo(restaurant.timezone))
    saluto = "Buongiorno" if local_now.hour < 14 else "Buonasera"
    if restaurant.custom_greeting and restaurant.custom_greeting.strip():
        return restaurant.custom_greeting.strip().replace("{saluto}", saluto)
    return f"{saluto}, {restaurant.name}. Come posso aiutarla?"


def build_twilio_personalization_response(
    restaurant: Restaurant,
    payload: TwilioPersonalizationRequest,
) -> TwilioPersonalizationResponse:
    turni_description = ", ".join(
        f"{turno['name']}: {turno['start']}-{turno['end']}"
        for turno in restaurant.turni
    )
    opening_hours_str = ", ".join(
        f"{k}: {v}" for k, v in (restaurant.opening_hours or {}).items()
    )
    weekly_closures_str = ", ".join(restaurant.weekly_closures or []) or "nessuna"
    closure_dates_str = ", ".join(restaurant.closure_dates or []) or "nessuna"
    local_now = datetime.now(ZoneInfo(restaurant.timezone))
    dynamic_variables = {
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "address": restaurant.address or "",
        "opening_hours": opening_hours_str,
        "weekly_closures": weekly_closures_str,
        "closure_dates": closure_dates_str,
        "turni_description": turni_description,
        "large_group_threshold": str(restaurant.booking_rules.get("large_group_threshold", 8)),
        "caller_phone": payload.caller_id,
        "called_number": payload.called_number,
        "call_sid": payload.call_sid,
        "timezone": restaurant.timezone,
        "current_date": local_now.strftime("%Y-%m-%d"),
        "current_time": local_now.strftime("%H:%M"),
        "current_day_of_week": local_now.strftime("%A"),
        "escalation_phone": restaurant.escalation_phone or "",
        "agent_style_notes": restaurant.agent_style_notes or "",
        "greeting": _greeting_for_restaurant(restaurant),
    }
    return TwilioPersonalizationResponse(
        dynamic_variables=dynamic_variables,
    )


def resolve_restaurant_for_inbound_call(
    db: Session,
    payload: TwilioPersonalizationRequest,
) -> Restaurant:
    restaurant = db.scalar(
        select(Restaurant).where(
            (Restaurant.elevenlabs_agent_id == payload.agent_id)
            | (Restaurant.twilio_phone == payload.called_number)
        )
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found for inbound call")
    return restaurant


@router.post("/twilio-personalization", response_model=TwilioPersonalizationResponse)
def twilio_personalization(
    payload: TwilioPersonalizationRequest,
    db: Session = Depends(get_db),
) -> TwilioPersonalizationResponse:
    restaurant = resolve_restaurant_for_inbound_call(db, payload)
    return build_twilio_personalization_response(restaurant, payload)
