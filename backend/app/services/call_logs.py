from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.cache import analytics_cache
from app.core.database import SessionLocal
from app.core.observability import json_log
from app.core.security import hash_phone
from app.integrations.elevenlabs import elevenlabs_service
from app.models import Booking, BookingEvent, CallLog, RawWebhookEvent, Restaurant
from app.schemas.common import CallOutcome, CallStatus, RawWebhookEventStatus

WEBHOOK_SOURCE_ELEVENLABS_POST_CALL = "elevenlabs_post_call"


def extract_transcript_preview(payload: dict[str, Any]) -> str | None:
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


def determine_outcome_from_db(
    db: Session, *, restaurant_id: str, call_start: datetime, call_duration: int
) -> tuple[str, str | None]:
    window_start = call_start - timedelta(seconds=30)
    window_end = call_start + timedelta(seconds=call_duration + 60)

    booking = db.scalar(
        select(Booking).where(
            Booking.restaurant_id == restaurant_id,
            Booking.source == "ai_phone",
            Booking.created_at >= window_start,
            Booking.created_at <= window_end,
        ).order_by(Booking.created_at.desc())
    )
    if booking:
        cancel_event = db.scalar(
            select(BookingEvent).where(
                BookingEvent.booking_id == booking.id,
                BookingEvent.event_type == "cancelled",
                BookingEvent.created_at >= window_start,
                BookingEvent.created_at <= window_end,
            )
        )
        if cancel_event:
            return CallOutcome.booking_cancelled, booking.id

        modify_event = db.scalar(
            select(BookingEvent).where(
                BookingEvent.booking_id == booking.id,
                BookingEvent.event_type == "modified",
                BookingEvent.created_at >= window_start,
                BookingEvent.created_at <= window_end,
            )
        )
        if modify_event:
            return CallOutcome.booking_modified, booking.id
        return CallOutcome.booking_created, booking.id

    return CallOutcome.info_provided, None


def determine_outcome_from_summary(summary: str) -> str:
    lowered = summary.lower()
    if "cancell" in lowered:
        return CallOutcome.booking_cancelled
    if "modific" in lowered:
        return CallOutcome.booking_modified
    if "trasfer" in lowered or "collega" in lowered or "transfer" in lowered:
        return CallOutcome.escalated
    if "silenz" in lowered or "richiam" in lowered or "abandon" in lowered:
        return CallOutcome.abandoned
    return CallOutcome.info_provided


def _normalize_call_status(*, raw_status: str | None = None, raw_success: str | None = None) -> str:
    lowered_status = (raw_status or "").lower().strip()
    lowered_success = (raw_success or "").lower().strip()
    if lowered_success == "failure":
        return CallStatus.failed
    if lowered_success == "success":
        return CallStatus.successful
    if "fail" in lowered_status or "error" in lowered_status:
        return CallStatus.failed
    if "success" in lowered_status or lowered_status == "done":
        return CallStatus.successful
    return CallStatus.unknown


def _elevenlabs_analysis_says_booked(analysis: dict[str, Any]) -> bool:
    """Check if ElevenLabs evaluation criteria indicate a reservation was completed."""
    criteria = analysis.get("evaluation_criteria_results", {})
    reservation = criteria.get("reservation_completed", {})
    return reservation.get("result") == "success"


def build_webhook_event_key(payload: dict[str, Any]) -> str:
    conversation_id = payload.get("conversation_id") or payload.get("id")
    if conversation_id:
        return str(conversation_id)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enqueue_raw_webhook_event(
    db: Session,
    *,
    source: str,
    payload: dict[str, Any],
) -> RawWebhookEvent:
    event_key = build_webhook_event_key(payload)
    event = db.scalar(
        select(RawWebhookEvent).where(
            RawWebhookEvent.source == source,
            RawWebhookEvent.event_key == event_key,
        )
    )
    if not event:
        event = RawWebhookEvent(
            source=source,
            event_key=event_key,
            raw_payload=payload,
            status=RawWebhookEventStatus.pending,
        )
        db.add(event)
        db.flush()
        return event

    event.raw_payload = payload
    event.received_at = datetime.now(UTC)
    if event.status == RawWebhookEventStatus.failed:
        event.status = RawWebhookEventStatus.pending
        event.last_error = None
        event.processed_at = None
    db.add(event)
    db.flush()
    return event


def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _resolve_restaurant_for_payload(db: Session, payload: dict[str, Any]) -> Restaurant | None:
    metadata = _payload_metadata(payload)
    agent_id = metadata.get("agent_id") or payload.get("agent_id")
    called_number = metadata.get("called_number") or payload.get("called_number")
    if not agent_id and not called_number:
        return None
    return db.scalar(
        select(Restaurant).where(
            (Restaurant.elevenlabs_agent_id == agent_id) | (Restaurant.twilio_phone == called_number)
        )
    )


_STALE_PROCESSING_SECONDS = 60


def recover_stale_processing_events(db: Session) -> int:
    """Reset events stuck in 'processing' for more than 60s back to 'pending'."""
    cutoff = datetime.now(UTC) - timedelta(seconds=_STALE_PROCESSING_SECONDS)
    stale_events = db.scalars(
        select(RawWebhookEvent).where(
            RawWebhookEvent.status == RawWebhookEventStatus.processing,
            RawWebhookEvent.received_at < cutoff,
        )
    ).all()
    recovered = 0
    for event in stale_events:
        event.status = RawWebhookEventStatus.pending
        event.last_error = "recovered from stale processing state"
        db.add(event)
        recovered += 1
    if recovered:
        db.commit()
        json_log("app.webhooks", {"event": "stale_events_recovered", "count": recovered})
    return recovered


def process_webhook_event(db: Session, *, event: RawWebhookEvent, request_id: str | None = None) -> bool:
    if event.status == RawWebhookEventStatus.done:
        return True
    if event.status == RawWebhookEventStatus.processing:
        return False

    event.status = RawWebhookEventStatus.processing
    db.add(event)
    db.commit()

    try:
        payload = event.raw_payload if isinstance(event.raw_payload, dict) else {}
        restaurant = _resolve_restaurant_for_payload(db, payload)
        if not restaurant:
            raise LookupError("Restaurant not found for webhook event")

        call_log = upsert_call_log_from_payload(db, restaurant=restaurant, payload=payload)
        event.restaurant_id = restaurant.id
        event.status = RawWebhookEventStatus.done
        event.processed_at = datetime.now(UTC)
        event.last_error = None
        db.add(event)
        db.commit()

        analytics_cache.invalidate(f"overview:{restaurant.id}")
        analytics_cache.invalidate(f"trends:{restaurant.id}")
        json_log(
            "app.webhooks",
            {
                "event": "raw_webhook_event_processed",
                "request_id": request_id,
                "raw_event_id": event.id,
                "restaurant_id": restaurant.id,
                "conversation_id": call_log.elevenlabs_conversation_id,
                "outcome": call_log.outcome,
                "pending_events": count_pending_webhook_events(
                    db, source=WEBHOOK_SOURCE_ELEVENLABS_POST_CALL
                ),
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        persisted = db.get(RawWebhookEvent, event.id)
        if not persisted:
            return False
        persisted.status = RawWebhookEventStatus.failed
        persisted.attempt_count += 1
        persisted.last_error = str(exc)
        persisted.processed_at = None
        db.add(persisted)
        db.commit()
        json_log(
            "app.webhooks",
            {
                "event": "raw_webhook_event_failed",
                "request_id": request_id,
                "raw_event_id": event.id,
                "error": str(exc),
                "attempt_count": persisted.attempt_count,
            },
        )
        return False


def process_webhook_event_now(event_id: str, request_id: str | None = None) -> bool:
    db = SessionLocal()
    try:
        event = db.get(RawWebhookEvent, event_id)
        if not event:
            return False
        return process_webhook_event(db, event=event, request_id=request_id)
    finally:
        db.close()


def count_pending_webhook_events(db: Session, *, source: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(RawWebhookEvent)
            .where(
                RawWebhookEvent.source == source,
                RawWebhookEvent.status.in_(
                    [RawWebhookEventStatus.pending, RawWebhookEventStatus.failed]
                ),
            )
        )
        or 0
    )


def _payload_matches_restaurant(payload: dict[str, Any], restaurant: Restaurant) -> bool:
    metadata = _payload_metadata(payload)
    agent_id = metadata.get("agent_id") or payload.get("agent_id")
    called_number = metadata.get("called_number") or payload.get("called_number")
    return bool(
        (restaurant.elevenlabs_agent_id and agent_id == restaurant.elevenlabs_agent_id)
        or (restaurant.twilio_phone and called_number == restaurant.twilio_phone)
    )


def replay_webhook_events(
    db: Session,
    *,
    source: str,
    restaurant: Restaurant | None = None,
    limit: int = 100,
    request_id: str | None = None,
) -> tuple[int, int]:
    stmt: Select[tuple[RawWebhookEvent]] = (
        select(RawWebhookEvent)
        .where(
            RawWebhookEvent.source == source,
            RawWebhookEvent.status.in_([RawWebhookEventStatus.pending, RawWebhookEventStatus.failed]),
        )
        .order_by(RawWebhookEvent.received_at.asc())
        .limit(limit)
    )
    events = db.scalars(stmt).all()
    replayed = 0
    failed = 0
    for event in events:
        if restaurant and event.restaurant_id not in {None, restaurant.id}:
            continue
        payload = event.raw_payload if isinstance(event.raw_payload, dict) else {}
        if (
            restaurant
            and event.restaurant_id == restaurant.id
            and not _payload_matches_restaurant(payload, restaurant)
        ):
            continue
        if process_webhook_event(db, event=event, request_id=request_id):
            replayed += 1
        else:
            failed += 1
    return replayed, failed


def upsert_call_log_from_payload(
    db: Session,
    *,
    restaurant: Restaurant,
    payload: dict[str, Any],
) -> CallLog:
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    analysis = payload.get("analysis", {}) if isinstance(payload, dict) else {}
    summary = analysis.get("transcript_summary") or payload.get("summary") or "Chiamata registrata"
    conversation_id = payload.get("conversation_id") or payload.get("id")
    if not conversation_id:
        raise ValueError("Missing conversation_id in payload")

    caller_id = metadata.get("caller_id") or payload.get("caller_id")
    started_at = metadata.get("start_time_unix_secs")
    started_dt = (
        datetime.fromtimestamp(started_at, tz=UTC)
        if isinstance(started_at, (int, float))
        else datetime.now(UTC)
    )
    duration = int(payload.get("call_duration_secs") or metadata.get("call_duration_secs") or 0)
    call_status = _normalize_call_status(
        raw_status=payload.get("call_status") or payload.get("status"),
        raw_success=payload.get("call_successful"),
    )
    transcript_text = str(payload.get("transcript") or "")
    has_tool_error = "tool failed" in transcript_text.lower() or "tool_error" in str(analysis).lower()

    db_outcome, linked_booking_id = determine_outcome_from_db(
        db, restaurant_id=restaurant.id, call_start=started_dt, call_duration=duration
    )
    if db_outcome == CallOutcome.info_provided:
        # Trust ElevenLabs evaluation criteria as a secondary signal
        if _elevenlabs_analysis_says_booked(analysis):
            db_outcome = CallOutcome.booking_created
        else:
            fallback = determine_outcome_from_summary(summary)
            if fallback in {CallOutcome.escalated, CallOutcome.abandoned}:
                db_outcome = fallback
    if db_outcome == CallOutcome.info_provided and has_tool_error:
        db_outcome = CallOutcome.tool_error

    call_log = db.scalar(select(CallLog).where(CallLog.elevenlabs_conversation_id == conversation_id))
    if not call_log:
        call_log = CallLog(restaurant_id=restaurant.id, elevenlabs_conversation_id=conversation_id)

    call_log.caller_phone_hash = hash_phone(caller_id) if caller_id else None
    call_log.started_at = started_dt
    call_log.duration_seconds = duration
    call_log.outcome = db_outcome
    call_log.call_status = call_status
    call_log.booking_id = linked_booking_id
    call_log.summary = summary
    call_log.transcript_preview = extract_transcript_preview(payload)
    call_log.extra_data = {
        "analysis": analysis,
        "metadata": metadata,
    }
    db.add(call_log)
    return call_log


def build_payload_from_conversation(conversation: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(conversation.get("metadata") or {})
    analysis = dict(conversation.get("analysis") or {})
    initiation = conversation.get("conversation_initiation_client_data") or {}
    dynamic_variables = initiation.get("dynamic_variables") or {}
    phone_call = metadata.get("phone_call") or {}

    caller_id = (
        dynamic_variables.get("caller_phone")
        or dynamic_variables.get("system__caller_id")
        or phone_call.get("external_number")
    )
    called_number = (
        dynamic_variables.get("called_number")
        or dynamic_variables.get("system__called_number")
        or phone_call.get("agent_number")
    )
    if caller_id:
        metadata.setdefault("caller_id", caller_id)
    if called_number:
        metadata.setdefault("called_number", called_number)
    if conversation.get("agent_id"):
        metadata.setdefault("agent_id", conversation["agent_id"])

    transcript_summary = (
        analysis.get("transcript_summary")
        or conversation.get("transcript_summary")
        or conversation.get("call_summary_title")
    )
    if transcript_summary:
        analysis.setdefault("transcript_summary", transcript_summary)

    return {
        "conversation_id": conversation.get("conversation_id"),
        "agent_id": conversation.get("agent_id"),
        "called_number": called_number,
        "caller_id": caller_id,
        "status": conversation.get("status"),
        "call_successful": conversation.get("call_successful"),
        "summary": transcript_summary,
        "call_duration_secs": conversation.get("call_duration_secs"),
        "metadata": metadata,
        "analysis": analysis,
        "transcript": conversation.get("transcript"),
    }


def sync_recent_calls_from_elevenlabs(
    db: Session,
    *,
    restaurant: Restaurant,
    days: int,
    request_id: str | None = None,
) -> int:
    if not restaurant.elevenlabs_agent_id:
        return 0

    start_dt = datetime.now(UTC) - timedelta(days=days)
    conversations = elevenlabs_service.list_recent_conversations(
        agent_id=restaurant.elevenlabs_agent_id,
        call_start_after_unix=int(start_dt.timestamp()),
    )
    if not conversations:
        return 0

    candidate_ids = [
        item.get("conversation_id")
        for item in conversations
        if item.get("conversation_id")
        and item.get("conversation_initiation_source") == "twilio"
        and ((item.get("direction") or "inbound") == "inbound")
    ]
    if not candidate_ids:
        return 0

    existing_ids = set(
        db.scalars(
            select(CallLog.elevenlabs_conversation_id).where(
                CallLog.elevenlabs_conversation_id.in_(candidate_ids)
            )
        ).all()
    )

    synced = 0
    for item in conversations:
        conversation_id = item.get("conversation_id")
        if (
            not conversation_id
            or conversation_id in existing_ids
            or item.get("conversation_initiation_source") != "twilio"
            or (item.get("direction") or "inbound") != "inbound"
        ):
            continue

        conversation = elevenlabs_service.fetch_conversation(conversation_id)
        if not conversation:
            continue
        for key in (
            "call_successful",
            "status",
            "conversation_initiation_source",
            "direction",
            "transcript_summary",
        ):
            if not conversation.get(key) and item.get(key) is not None:
                conversation[key] = item.get(key)
        payload = build_payload_from_conversation(conversation)
        called_number = (
            payload.get("called_number")
            or (payload.get("metadata") or {}).get("called_number")
        )
        if restaurant.twilio_phone and called_number and called_number != restaurant.twilio_phone:
            continue
        upsert_call_log_from_payload(db, restaurant=restaurant, payload=payload)
        synced += 1
        existing_ids.add(conversation_id)

    if synced:
        db.commit()
        json_log(
            "app.calls",
            {
                "event": "recent_calls_backfilled",
                "request_id": request_id,
                "restaurant_id": restaurant.id,
                "synced_count": synced,
            },
        )
    return synced
