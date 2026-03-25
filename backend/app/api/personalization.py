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
    assistant_settings = restaurant.assistant_settings or {}
    custom_greeting = assistant_settings.get("custom_greeting")
    if isinstance(custom_greeting, str) and custom_greeting.strip():
        return custom_greeting.strip()
    local_now = datetime.now(ZoneInfo(restaurant.timezone))
    greeting = "Buongiorno" if local_now.hour < 14 else "Buonasera"
    return f"{greeting}, {restaurant.name}. Come posso aiutarla?"


@router.post("/twilio-personalization", response_model=TwilioPersonalizationResponse)
def twilio_personalization(
    payload: TwilioPersonalizationRequest,
    db: Session = Depends(get_db),
) -> TwilioPersonalizationResponse:
    restaurant = db.scalar(
        select(Restaurant).where(
            (Restaurant.elevenlabs_agent_id == payload.agent_id)
            | (Restaurant.twilio_phone == payload.called_number)
        )
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found for inbound call")

    turni_description = ", ".join(
        f"{turno['name']}: {turno['start']}-{turno['end']}"
        for turno in restaurant.turni
    )
    assistant_settings = restaurant.assistant_settings or {}
    dynamic_variables = {
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "address": restaurant.address,
        "opening_hours": restaurant.opening_hours,
        "weekly_closures": restaurant.weekly_closures,
        "turni_description": turni_description,
        "large_group_threshold": restaurant.booking_rules.get("large_group_threshold", 8),
        "caller_phone": payload.caller_id,
        "called_number": payload.called_number,
        "call_sid": payload.call_sid,
        "timezone": restaurant.timezone,
        "llm_provider": assistant_settings.get("llm_provider", "openai"),
        "openai_model": assistant_settings.get("openai_model", "gpt-5-mini"),
        "reasoning_effort": assistant_settings.get("reasoning_effort", "minimal"),
        "response_verbosity": assistant_settings.get("response_verbosity", "low"),
        "agent_style_notes": assistant_settings.get("agent_style_notes"),
        "greeting": _greeting_for_restaurant(restaurant),
    }
    return TwilioPersonalizationResponse(
        dynamic_variables=dynamic_variables,
        conversation_config_override={
            "agent": {
                "first_message": dynamic_variables["greeting"],
            }
        },
    )
