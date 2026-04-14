from __future__ import annotations

from app.schemas.common import AppBaseModel, CallOutcome, CallStatus, VoiceProvider


class CallLogRead(AppBaseModel):
    id: str
    restaurant_id: str
    voice_provider: VoiceProvider
    provider_call_id: str | None = None
    twilio_call_sid: str | None = None
    started_at: str
    duration_seconds: int
    outcome: CallOutcome
    call_status: CallStatus = CallStatus.unknown
    booking_id: str | None = None
    summary: str
    transcript_preview: str | None = None
    caller_phone: str | None = None


class TranscriptResponse(AppBaseModel):
    call_id: str
    source: str
    summary: str
    transcript: str | None = None
    metadata: dict


class CallSyncResponse(AppBaseModel):
    replayed_events: int
    failed_events: int
    pending_events: int
    backfilled_calls: int
