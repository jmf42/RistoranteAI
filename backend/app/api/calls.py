from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from app.api.deps import (
    accessible_restaurant_id,
    get_current_user,
    get_db,
    get_restaurant_or_404,
    require_roles,
)
from app.core.observability import json_log
from app.models import CallLog, User
from app.schemas.calls import CallLogRead, CallSyncResponse, TranscriptResponse

router = APIRouter(prefix="/calls", tags=["calls"])


def _call_to_read(call: CallLog) -> CallLogRead:
    return CallLogRead(
        id=call.id,
        restaurant_id=call.restaurant_id,
        voice_provider=call.voice_provider,
        provider_call_id=call.provider_call_id,
        twilio_call_sid=call.twilio_call_sid,
        started_at=call.started_at.isoformat(),
        duration_seconds=call.duration_seconds,
        outcome=call.outcome,
        call_status=call.call_status or "unknown",
        booking_id=call.booking_id,
        summary=call.summary,
        transcript_preview=call.transcript_preview,
    )


@router.get("", response_model=list[CallLogRead])
def list_calls(
    restaurant_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    days: int = Query(default=14, ge=1, le=90),
    search: str | None = Query(default=None),
    attention_only: bool = Query(default=False),
    sort: str = Query(default="newest", pattern="^(newest|longest|follow_up)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CallLogRead]:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    start_dt = datetime.now(UTC) - timedelta(days=days)
    stmt = select(CallLog).where(CallLog.restaurant_id == resolved_id, CallLog.started_at >= start_dt)
    if outcome:
        stmt = stmt.where(CallLog.outcome == outcome)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                CallLog.summary.ilike(pattern),
                CallLog.transcript_preview.ilike(pattern),
                CallLog.booking_id.ilike(pattern),
                CallLog.provider_call_id.ilike(pattern),
                CallLog.twilio_call_sid.ilike(pattern),
            )
        )
    if attention_only:
        stmt = stmt.where(
            or_(
                CallLog.call_status == "failed",
                CallLog.outcome == "tool_error",
                CallLog.outcome == "abandoned",
            )
        )

    if sort == "longest":
        stmt = stmt.order_by(CallLog.duration_seconds.desc(), CallLog.started_at.desc())
    elif sort == "follow_up":
        follow_up_rank = case(
            (
                or_(
                    CallLog.call_status == "failed",
                    CallLog.outcome == "tool_error",
                    CallLog.outcome == "abandoned",
                ),
                0,
            ),
            else_=1,
        )
        stmt = stmt.order_by(follow_up_rank.asc(), CallLog.started_at.desc())
    else:
        stmt = stmt.order_by(CallLog.started_at.desc())

    calls = db.scalars(stmt.limit(250)).all()
    return [_call_to_read(call) for call in calls]


@router.post("/sync", response_model=CallSyncResponse)
def sync_calls(
    request: Request,
    restaurant_id: str | None = Query(default=None),
    days: int = Query(default=2, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner")),
) -> CallSyncResponse:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    restaurant = get_restaurant_or_404(db, resolved_id)
    request_id = getattr(request.state, "request_id", None)
    json_log(
        "app.calls",
        {
            "event": "manual_calls_sync",
            "request_id": request_id,
            "restaurant_id": restaurant.id,
            "days": days,
            "replayed_events": 0,
            "failed_events": 0,
            "backfilled_calls": 0,
            "pending_events": 0,
            "user_email": current_user.email,
        },
    )
    return CallSyncResponse(
        replayed_events=0,
        failed_events=0,
        pending_events=0,
        backfilled_calls=0,
    )


@router.get("/export")
def export_calls(
    restaurant_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    start_dt = datetime.now(UTC) - timedelta(days=days)
    stmt = select(CallLog).where(CallLog.restaurant_id == resolved_id, CallLog.started_at >= start_dt)
    if outcome:
        stmt = stmt.where(CallLog.outcome == outcome)
    calls = db.scalars(stmt.order_by(CallLog.started_at.desc()).limit(2000)).all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "started_at",
            "duration_seconds",
            "outcome",
            "summary",
            "booking_id",
            "provider_call_id",
            "twilio_call_sid",
        ]
    )
    for call in calls:
        writer.writerow(
            [
                call.started_at.isoformat(),
                call.duration_seconds,
                call.outcome,
                call.summary,
                call.booking_id or "",
                call.provider_call_id or "",
                call.twilio_call_sid or "",
            ]
        )
    filename = f"calls-{datetime.now(UTC).date().isoformat()}.csv"
    json_log(
        "app.audit",
        {
            "event": "data_export",
            "export_type": "calls_csv",
            "user_email": current_user.email,
            "restaurant_id": resolved_id,
            "record_count": len(calls),
        },
    )
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{call_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    call_id: str,
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TranscriptResponse:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    call = db.scalar(select(CallLog).where(CallLog.id == call_id, CallLog.restaurant_id == resolved_id))
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return TranscriptResponse(
        call_id=call.id,
        source=call.voice_provider,
        summary=call.summary,
        transcript=call.transcript_preview,
        metadata=call.extra_data or {},
    )
