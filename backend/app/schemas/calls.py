from __future__ import annotations

from app.schemas.common import AppBaseModel, CallOutcome, CallStatus


class CallLogRead(AppBaseModel):
    id: str
    restaurant_id: str
    elevenlabs_conversation_id: str | None = None
    started_at: str
    duration_seconds: int
    outcome: CallOutcome
    call_status: CallStatus = CallStatus.unknown
    booking_id: str | None = None
    summary: str
    transcript_preview: str | None = None


class TranscriptResponse(AppBaseModel):
    call_id: str
    source: str
    summary: str
    transcript: str | None = None
    metadata: dict
