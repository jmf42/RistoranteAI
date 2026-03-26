from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.deps import get_db
from app.core.observability import json_log
from app.models import Restaurant

router = APIRouter(prefix="/twilio", tags=["twilio"])


def _twiml_response(body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        media_type="application/xml",
    )


@router.post("/voice-fallback")
async def voice_fallback(request: Request, db: Session = Depends(get_db)) -> Response:
    form = await request.form()
    called_number = str(form.get("Called") or form.get("To") or "").strip()
    caller_number = str(form.get("From") or "").strip()

    restaurant = None
    if called_number:
        restaurant = db.scalar(select(Restaurant).where(Restaurant.twilio_phone == called_number))

    json_log(
        "app.twilio",
        {
            "event": "twilio_voice_fallback_invoked",
            "request_id": getattr(request.state, "request_id", None),
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
