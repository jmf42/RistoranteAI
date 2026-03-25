from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db
from app.integrations.elevenlabs import elevenlabs_service
from app.models import CallLog, User
from app.schemas.calls import CallLogRead, TranscriptResponse

router = APIRouter(prefix="/calls", tags=["calls"])


def _call_to_read(call: CallLog) -> CallLogRead:
    return CallLogRead(
        id=call.id,
        restaurant_id=call.restaurant_id,
        elevenlabs_conversation_id=call.elevenlabs_conversation_id,
        started_at=call.started_at.isoformat(),
        duration_seconds=call.duration_seconds,
        outcome=call.outcome,
        booking_id=call.booking_id,
        summary=call.summary,
        transcript_preview=call.transcript_preview,
    )


@router.get("", response_model=list[CallLogRead])
def list_calls(
    restaurant_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CallLogRead]:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    start_dt = datetime.now(UTC) - timedelta(days=days)
    stmt = select(CallLog).where(CallLog.restaurant_id == resolved_id, CallLog.started_at >= start_dt)
    if outcome:
        stmt = stmt.where(CallLog.outcome == outcome)
    calls = db.scalars(stmt.order_by(CallLog.started_at.desc()).limit(250)).all()
    return [_call_to_read(call) for call in calls]


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
            "elevenlabs_conversation_id",
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
                call.elevenlabs_conversation_id or "",
            ]
        )
    filename = f"calls-{datetime.now(UTC).date().isoformat()}.csv"
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
    remote = None
    if call.elevenlabs_conversation_id:
        remote = elevenlabs_service.fetch_conversation_transcript(call.elevenlabs_conversation_id)
    if remote:
        analysis = remote.get("analysis") if isinstance(remote.get("analysis"), dict) else {}
        return TranscriptResponse(
            call_id=call.id,
            source="elevenlabs",
            summary=analysis.get("transcript_summary") or call.summary,
            transcript=remote.get("transcript"),
            metadata={key: value for key, value in remote.items() if key != "transcript"},
        )
    return TranscriptResponse(
        call_id=call.id,
        source="local-preview",
        summary=call.summary,
        transcript=call.transcript_preview,
        metadata=call.extra_data or {},
    )
