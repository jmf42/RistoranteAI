from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.observability import json_log
from app.core.security import hash_phone
from app.integrations.elevenlabs import elevenlabs_service
from app.models import CallLog, Restaurant

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _extract_transcript_preview(payload: dict) -> str | None:
    transcript = payload.get("transcript")
    if isinstance(transcript, str):
        return transcript[:2000]
    if isinstance(transcript, list):
        parts = []
        for entry in transcript[:20]:
            speaker = entry.get("speaker") or entry.get("role") or "speaker"
            text = entry.get("text") or entry.get("message") or ""
            if text:
                parts.append(f"{speaker}: {text}")
        return "\n".join(parts)[:2000]
    return None


def _determine_outcome(summary: str) -> str:
    from app.schemas.common import CallOutcome

    lowered = summary.lower()
    if "cancell" in lowered:
        return CallOutcome.booking_cancelled
    if "modific" in lowered:
        return CallOutcome.booking_modified
    if "prenot" in lowered or "booking" in lowered:
        return CallOutcome.booking_created
    if "trasfer" in lowered or "collega" in lowered:
        return CallOutcome.escalated
    if "silenz" in lowered or "richiam" in lowered:
        return CallOutcome.abandoned
    return CallOutcome.info_provided


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
    analysis = body.get("analysis", {}) if isinstance(body, dict) else {}
    agent_id = metadata.get("agent_id") or body.get("agent_id")
    called_number = metadata.get("called_number") or body.get("called_number")
    restaurant = db.scalar(
        select(Restaurant).where(
            (Restaurant.elevenlabs_agent_id == agent_id) | (Restaurant.twilio_phone == called_number)
        )
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    summary = analysis.get("transcript_summary") or body.get("summary") or "Chiamata registrata"
    conversation_id = body.get("conversation_id") or body.get("id")
    if not conversation_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing conversation_id in payload",
        )
    caller_id = metadata.get("caller_id") or body.get("caller_id")
    started_at = metadata.get("start_time_unix_secs")
    started_dt = (
        datetime.fromtimestamp(started_at, tz=UTC)
        if isinstance(started_at, (int, float))
        else datetime.now(UTC)
    )

    try:
        call_log = db.scalar(
            select(CallLog).where(CallLog.elevenlabs_conversation_id == conversation_id)
        )
        if not call_log:
            call_log = CallLog(restaurant_id=restaurant.id, elevenlabs_conversation_id=conversation_id)
        call_log.caller_phone_hash = hash_phone(caller_id) if caller_id else None
        call_log.started_at = started_dt
        call_log.duration_seconds = int(body.get("call_duration_secs") or metadata.get("call_duration_secs") or 0)
        call_log.outcome = _determine_outcome(summary)
        call_log.summary = summary
        call_log.transcript_preview = _extract_transcript_preview(body)
        call_log.extra_data = {
            "analysis": analysis,
            "metadata": metadata,
        }
        db.add(call_log)
        db.commit()
    except Exception:
        db.rollback()
        raise
    json_log(
        "app.webhooks",
        {
            "event": "elevenlabs_post_call_processed",
            "request_id": getattr(request.state, "request_id", None),
            "restaurant_id": restaurant.id,
            "conversation_id": conversation_id,
            "outcome": call_log.outcome,
        },
    )
    return {"status": "received"}
