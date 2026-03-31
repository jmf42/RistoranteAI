from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.observability import json_log
from app.integrations.elevenlabs import elevenlabs_service
from app.services.call_logs import (
    WEBHOOK_SOURCE_ELEVENLABS_POST_CALL,
    count_pending_webhook_events,
    enqueue_raw_webhook_event,
    process_webhook_event_now,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/elevenlabs/post-call")
async def elevenlabs_post_call(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
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
    if not isinstance(body, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook body")

    raw_event = enqueue_raw_webhook_event(
        db,
        source=WEBHOOK_SOURCE_ELEVENLABS_POST_CALL,
        payload=body,
    )
    db.commit()
    request_id = getattr(request.state, "request_id", None)
    background_tasks.add_task(process_webhook_event_now, raw_event.id, request_id)

    json_log(
        "app.webhooks",
        {
            "event": "elevenlabs_post_call_received",
            "request_id": request_id,
            "raw_event_id": raw_event.id,
            "event_key": raw_event.event_key,
            "pending_events": count_pending_webhook_events(
                db, source=WEBHOOK_SOURCE_ELEVENLABS_POST_CALL
            ),
        },
    )
    return {"status": "received"}
