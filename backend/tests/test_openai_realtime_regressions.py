from __future__ import annotations

import base64
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import CallLog, Restaurant
from app.services.openai_realtime import (
    RealtimeCallState,
    RealtimeSessionOverrides,
    _buffer_twilio_media_payload,
    _build_final_call_summary,
    _build_final_conversation_summary,
    _ingest_assistant_transcript,
    _ingest_user_transcript,
    _sync_dispatch_tool,
    build_realtime_instructions,
    studio_prompt_diagnostics,
)


def _next_open_date() -> str:
    candidate = date.today() + timedelta(days=5)
    while candidate.strftime("%A").lower() == "monday":
        candidate += timedelta(days=1)
    return candidate.isoformat()


def test_prompt_diagnostics_warn_when_prompt_drifts_from_restaurant_context(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    prompt = (
        "Role & Objective\n- Test.\n\n"
        "Language\n- Se il cliente parla chiaramente un'altra lingua che sai gestire, segui la lingua del cliente.\n\n"
        "Context\n"
        '- Chiusure settimanali: ["Sunday evening"]\n'
        '- Orari: {"lunch": "12:00-15:00", "dinner": "19:00-23:30"}\n'
        '- Turni: [{"name": "Cena 1", "start": "19:00", "end": "21:00", "max_covers": 40}]\n\n'
        "Tools\n- Controllo subito.\n\n"
        "Write Action Rules\n- Conferma esplicita in turno separato.\n\n"
        "Safety & Escalation\n- La metto in contatto con il ristorante.\n\n"
        "Unclear Audio\n- Non inventare."
    )

    diagnostics = studio_prompt_diagnostics(
        prompt,
        restaurant=restaurant,
        effective_overrides=RealtimeSessionOverrides(),
    )

    drift = next(item for item in diagnostics if item["label"] == "Restaurant context drift")
    assert drift["status"] == "warn"


def test_prompt_diagnostics_warn_when_multilingual_prompt_conflicts_with_fixed_input_language(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    prompt = (
        "Role & Objective\n- Test.\n\n"
        "Language\n"
        "- Se il cliente parla chiaramente un'altra lingua che sai gestire, segui la lingua del cliente.\n"
        "- Apri in italiano solo come default iniziale.\n\n"
        "Tools\n- Controllo subito.\n\n"
        "Write Action Rules\n- Conferma esplicita in turno separato.\n\n"
        "Safety & Escalation\n- La metto in contatto con il ristorante.\n\n"
        "Unclear Audio\n- Non inventare."
    )

    diagnostics = studio_prompt_diagnostics(
        prompt,
        restaurant=restaurant,
        effective_overrides=RealtimeSessionOverrides(input_language="it"),
    )

    conflict = next(item for item in diagnostics if item["label"] == "Multilingual runtime conflict")
    assert conflict["status"] == "warn"


def test_default_prompt_keeps_info_calls_open_with_one_brief_follow_up(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.openai_prompt_override = None
    db_session.add(restaurant)
    db_session.commit()

    prompt = build_realtime_instructions(restaurant, caller_phone="+393401112233")

    assert "Dopo una risposta informativa completa, fai una sola breve apertura naturale" in prompt
    assert "Se vuole, posso anche aiutarla con una prenotazione." in prompt
    assert "Se il cliente non aggiunge altro o resta in silenzio, chiudi con cortesia." in prompt


def test_initial_greeting_audio_is_not_dropped_for_barge_in():
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_barge_in")
    payload = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    buffered_audio = bytearray()

    packets = _buffer_twilio_media_payload(
        state,
        payload=payload,
        buffered_audio=buffered_audio,
        buffered_packets=0,
    )

    assert packets == 1
    assert buffered_audio == b"\x00\x01\x02\x03"
    assert state.dropped_input_audio_packets == 0


def test_invalid_slot_reply_escalates_after_two_incompatible_answers():
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_invalid_slot")

    _ingest_assistant_transcript(
        state,
        "Per la cena abbiamo due fasce: dalle 19 alle 21 oppure dalle 21 in poi. Quale preferisce?",
    )
    _ingest_user_transcript(state, "Ciao.")
    assert state.last_user_reply_valid is False
    assert state.should_escalate is False

    _ingest_assistant_transcript(
        state,
        "Mi scusi, non ho capito bene la fascia. Preferisce dalle 19 o dalle 21?",
    )
    _ingest_user_transcript(state, "Va bene.")

    assert state.last_user_reply_valid is False
    assert state.should_escalate is True


def test_check_availability_normalizes_children_into_total_party_size(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_children_total")

    _ingest_user_transcript(state, "Siamo quattro con tre bambini.")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="check_availability",
        arguments={
            "date": _next_open_date(),
            "party_size": 4,
            "time_preference": "21:00:00",
        },
    )

    assert result["available"] is True
    assert result["normalized_party_size"] == 7


def test_check_availability_preserves_lunch_request_instead_of_rewriting_to_dinner(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.turni = [
        {"name": "Pranzo", "start": "12:00", "end": "15:00", "max_covers": 30},
        {"name": "Cena 1", "start": "19:00", "end": "21:00", "max_covers": 40},
        {"name": "Cena 2", "start": "21:00", "end": "23:30", "max_covers": 35},
    ]
    db_session.add(restaurant)
    db_session.commit()

    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_lunch_guard")
    _ingest_user_transcript(state, "Domani ore 12, tre persone.")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="check_availability",
        arguments={
            "date": _next_open_date(),
            "party_size": 3,
            "time_preference": "19:00:00",
        },
    )

    assert result["available"] is True
    assert result["slot"]["time"] == "12:00"
    assert result["normalized_time"] == "12:00:00"


def test_create_booking_is_blocked_when_caller_only_asked_for_options(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(caller_phone="+393409991111", twilio_call_sid="CA_options_only")

    _ingest_user_transcript(state, "Vorrei solo alcune opzioni per mercoledi a pranzo.")
    state.confirmation_granted = True

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": _next_open_date(),
            "time": "12:00:00",
            "party_size": 2,
            "customer_name": "Francesco",
        },
    )

    assert result["success"] is False
    assert "solo disponibilita" in result["reason"].lower()


def test_successful_create_booking_links_call_log_and_summary_uses_tool_truth(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    call_log = CallLog(
        restaurant_id=restaurant.id,
        voice_provider=restaurant.voice_provider,
        provider_call_id="sess_linked_booking",
        twilio_call_sid="CA_linked_booking",
        caller_phone_hash="hash",
        summary="Chiamata avviata.",
        transcript_preview="",
        extra_data={},
    )
    db_session.add(call_log)
    db_session.commit()

    state = RealtimeCallState(caller_phone="+393409991111", twilio_call_sid="CA_linked_booking")
    _ingest_user_transcript(state, "Vorrei prenotare per martedi alle 21 per due persone.")
    _ingest_assistant_transcript(
        state,
        "Martedi alle 21 per due persone a nome Luca. Confermo?",
    )
    _ingest_user_transcript(state, "Si, confermo")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": _next_open_date(),
            "time": "21:00:00",
            "party_size": 2,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is True
    assert result["booking_id"]
    assert state.current_booking_id == result["booking_id"]

    db_session.refresh(call_log)
    assert call_log.booking_id == result["booking_id"]

    state.tool_events.append(
        {
            "tool": "create_booking",
            "arguments": {
                "date": _next_open_date(),
                "time": "21:00:00",
                "party_size": 2,
                "customer_name": "Luca",
            },
            "result": result,
        }
    )
    state.outcome = "booking_created"

    assert "Prenotazione confermata" in _build_final_call_summary(state)
    assert "create_booking success=true" in _build_final_conversation_summary(state)
