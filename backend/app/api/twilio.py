from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.deps import get_db
from app.api.personalization import (
    build_twilio_personalization_response,
    resolve_restaurant_for_inbound_call,
)
from app.core.observability import json_log
from app.integrations.elevenlabs import elevenlabs_service
from app.models import Restaurant
from app.schemas.tools import TwilioPersonalizationRequest

router = APIRouter(prefix="/twilio", tags=["twilio"])


def _twiml_response(body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        media_type="application/xml",
    )


def _voice_fallback_response(
    *,
    db: Session,
    called_number: str,
    caller_number: str,
    request_id: str | None,
) -> Response:
    restaurant = None
    if called_number:
        restaurant = db.scalar(select(Restaurant).where(Restaurant.twilio_phone == called_number))

    json_log(
        "app.twilio",
        {
            "event": "twilio_voice_fallback_invoked",
            "request_id": request_id,
            "called_number": called_number or None,
            "caller_number_present": bool(caller_number),
            "restaurant_id": restaurant.id if restaurant else None,
        },
    )

    if restaurant and restaurant.escalation_phone:
        restaurant_name = escape(restaurant.name)
        escalation_phone = escape(restaurant.escalation_phone)
        return _twiml_response(
            f"<Say language=\"it-IT\" voice=\"alice\">"
            f"Ci scusi, stiamo avendo un problema tecnico con il centralino automatico di {restaurant_name}. "
            f"La metto subito in contatto con il ristorante."
            f"</Say>"
            f"<Dial>{escalation_phone}</Dial>"
        )

    return _twiml_response(
        "<Say language=\"it-IT\" voice=\"alice\">"
        "Ci scusi, stiamo avendo un problema tecnico con il centralino automatico. "
        "La invitiamo a richiamare tra qualche minuto."
        "</Say>"
        "<Hangup/>"
    )


@router.post("/inbound")
async def inbound_call(request: Request, db: Session = Depends(get_db)) -> Response:
    form = await request.form()
    from_number = str(form.get("From") or "").strip()
    to_number = str(form.get("To") or form.get("Called") or "").strip()
    call_sid = str(form.get("CallSid") or "").strip()

    payload = TwilioPersonalizationRequest(
        caller_id=from_number,
        called_number=to_number,
        call_sid=call_sid or "missing-call-sid",
        agent_id="",
    )

    try:
        restaurant = resolve_restaurant_for_inbound_call(db, payload)
    except Exception:  # noqa: BLE001
        json_log(
            "app.twilio",
            {
                "event": "twilio_inbound_restaurant_not_found",
                "request_id": getattr(request.state, "request_id", None),
                "from_number": from_number or None,
                "to_number": to_number or None,
            },
        )
        return _voice_fallback_response(
            db=db,
            called_number=to_number,
            caller_number=from_number,
            request_id=getattr(request.state, "request_id", None),
        )

    personalization = build_twilio_personalization_response(
        restaurant,
        payload.model_copy(update={"agent_id": restaurant.elevenlabs_agent_id or ""}),
    )

    try:
        twiml = elevenlabs_service.register_twilio_call(
            agent_id=restaurant.elevenlabs_agent_id or "",
            from_number=from_number,
            to_number=to_number,
            conversation_initiation_client_data=personalization.model_dump(mode="python", exclude_none=True),
            direction="inbound",
        )
    except Exception as exc:  # noqa: BLE001
        json_log(
            "app.twilio",
            {
                "event": "twilio_inbound_register_call_failed",
                "request_id": getattr(request.state, "request_id", None),
                "restaurant_id": restaurant.id,
                "from_number": from_number or None,
                "to_number": to_number or None,
                "error": str(exc),
            },
        )
        return _voice_fallback_response(
            db=db,
            called_number=to_number,
            caller_number=from_number,
            request_id=getattr(request.state, "request_id", None),
        )

    json_log(
        "app.twilio",
        {
            "event": "twilio_inbound_register_call_success",
            "request_id": getattr(request.state, "request_id", None),
            "restaurant_id": restaurant.id,
            "call_sid": call_sid or None,
        },
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice-fallback")
async def voice_fallback(request: Request, db: Session = Depends(get_db)) -> Response:
    form = await request.form()
    called_number = str(form.get("Called") or form.get("To") or "").strip()
    caller_number = str(form.get("From") or "").strip()
    return _voice_fallback_response(
        db=db,
        called_number=called_number,
        caller_number=caller_number,
        request_id=getattr(request.state, "request_id", None),
    )
