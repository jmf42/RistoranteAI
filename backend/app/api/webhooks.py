from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.cache import analytics_cache
from app.core.config import settings
from app.core.observability import json_log
from app.integrations.elevenlabs import elevenlabs_service
from app.models import Restaurant
from app.services.call_logs import upsert_call_log_from_payload

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/elevenlabs/post-call")
async def elevenlabs_post_call(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_payload = await request.body()
    try:
        body = json.loads(raw_payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from exc

    if settings.elevenlabs_webhook_secret:
        signature = request.headers.get("elevenlabs-signature")
        if not signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        try:
            event = elevenlabs_service.verify_webhook(raw_payload, signature)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature") from exc
        body = event.data if hasattr(event, "data") else body.get("data", body)
    else:
        body = body.get("data", body)

    metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
    agent_id = metadata.get("agent_id") or body.get("agent_id")
    called_number = metadata.get("called_number") or body.get("called_number")
    restaurant = db.scalar(
        select(Restaurant).where(
            (Restaurant.elevenlabs_agent_id == agent_id) | (Restaurant.twilio_phone == called_number)
        )
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    try:
        call_log = upsert_call_log_from_payload(db, restaurant=restaurant, payload=body)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Invalidate analytics cache for this restaurant since new call data arrived
    analytics_cache.invalidate(f"overview:{restaurant.id}")
    analytics_cache.invalidate(f"trends:{restaurant.id}")

    json_log(
        "app.webhooks",
        {
            "event": "elevenlabs_post_call_processed",
            "request_id": getattr(request.state, "request_id", None),
            "restaurant_id": restaurant.id,
            "conversation_id": call_log.elevenlabs_conversation_id,
            "outcome": call_log.outcome,
            "linked_booking_id": call_log.booking_id,
        },
    )
    return {"status": "received"}
