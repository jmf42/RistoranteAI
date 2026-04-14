from __future__ import annotations

import asyncio
import base64
from datetime import date, time, timedelta
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Booking, Restaurant
from app.schemas.booking import BookingCreate
from app.schemas.common import BookingSource, BookingStatus
from app.services.bookings import create_booking
from app.services.openai_realtime import (
    RealtimeCallState,
    RealtimeSessionOverrides,
    _append_transcript_line,
    _buffer_twilio_media_payload,
    _build_conversation_summary_prompt,
    _build_tool_scope_update,
    _finish_initial_greeting,
    _ingest_assistant_transcript,
    _ingest_input_audio_transcription_delta,
    _ingest_user_transcript,
    _run_silent_response_watchdog,
    _runtime_context_message,
    _send_response_create,
    _should_ignore_post_write_user_turn,
    _silent_response_retry_allowed,
    _successful_call_outcome,
    _sync_call_update,
    _sync_dispatch_tool,
    _sync_end_twilio_call,
    _write_confirmation_granted,
    build_realtime_tools,
    build_session_update,
    realtime_headers,
    realtime_ws_url,
)


def _next_open_date() -> str:
    candidate = date.today() + timedelta(days=5)
    while candidate.strftime("%A").lower() == "monday":
        candidate += timedelta(days=1)
    return candidate.isoformat()


def _next_open_date_after(d: date) -> str:
    """Return the next open date strictly after d, skipping Monday closures."""
    candidate = d + timedelta(days=1)
    while candidate.strftime("%A").lower() == "monday":
        candidate += timedelta(days=1)
    return candidate.isoformat()


def test_create_booking_tool_requires_explicit_confirmation(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(
        caller_phone="+393401112233",
        twilio_call_sid="CA_confirm_guard",
        last_user_transcript="sì",
        last_assistant_transcript="Per che giorno, a che ora e per quante persone?",
    )

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": _next_open_date(),
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is False
    assert "Conferma esplicita" in result["reason"]


def test_create_booking_tool_succeeds_after_confirmation(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    booking_date = _next_open_date()
    state = RealtimeCallState(
        caller_phone="+393409991111",
        twilio_call_sid="CA_confirm_ok",
    )
    _ingest_assistant_transcript(
        state, "5 aprile alle 20:00 per 2 persone a nome Luca. Confermo?"
    )
    _ingest_user_transcript(state, "Sì, confermo")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": booking_date,
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is True
    created = db_session.scalar(select(Booking).where(Booking.confirmation_code == result["confirmation_code"]))
    assert created is not None
    assert created.source == "ai_phone"


def test_realtime_ws_url_uses_selected_model() -> None:
    url = realtime_ws_url("gpt-realtime-1.5")
    assert "model=gpt-realtime-1.5" in url


def test_realtime_headers_use_authorization_only() -> None:
    with patch("app.services.openai_realtime.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key-123"
        headers = realtime_headers()
    assert headers == {"Authorization": "Bearer test-key-123"}


def test_silent_response_watchdog_ignores_closed_realtime_socket(db_session):
    class ClosedRealtimeWebSocket:
        async def send(self, _payload: str) -> None:
            raise RuntimeError("connection already closed")

    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(
        caller_phone="+393401112233",
        twilio_call_sid="CA_watchdog_closed",
    )
    state.response_in_progress = True
    state.response_audio_started = False

    with patch("app.services.openai_realtime.SILENT_RESPONSE_WATCHDOG_SECONDS", 0):
        asyncio.run(
            _run_silent_response_watchdog(
                realtime_ws=ClosedRealtimeWebSocket(),
                restaurant=restaurant,
                state=state,
                caller_phone="+393401112233",
                generation=state.response_watchdog_generation,
            )
        )


def test_session_update_uses_ga_session_shape(db_session):
    """Session payload should follow the GA-style shape expected by current Realtime docs."""
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    session = session_update["session"]
    audio = session["audio"]
    assert session["type"] == "realtime"
    assert audio["input"]["format"] == {"type": "audio/pcmu"}
    assert audio["output"]["format"] == {"type": "audio/pcmu"}
    assert audio["output"]["voice"] is not None
    assert audio["input"]["turn_detection"]["type"] == "server_vad"
    assert audio["input"]["turn_detection"]["idle_timeout_ms"] == 7000
    assert session["truncation"]["type"] == "retention_ratio"
    assert session["truncation"]["retention_ratio"] == 0.75
    assert audio["input"]["transcription"]["model"] == "gpt-4o-mini-transcribe"
    assert "language" not in audio["input"]["transcription"]
    assert session["parallel_tool_calls"] is False
    assert [tool["name"] for tool in session["tools"]] == [
        "check_availability",
        "find_booking",
        "escalate_to_human",
    ]
    assert "modalities" not in session
    assert "temperature" not in session
    assert "speed" not in session
    assert "max_response_output_tokens" not in session
    assert "token_limits" not in session["truncation"]
    assert "voice" not in session


def test_session_update_with_semantic_vad(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    overrides = RealtimeSessionOverrides(turn_detection_type="semantic_vad", semantic_vad_eagerness="high")
    session_update = build_session_update(restaurant, caller_phone="+390000000000", overrides=overrides)
    td = session_update["session"]["audio"]["input"]["turn_detection"]
    assert td["type"] == "semantic_vad"
    assert td["eagerness"] == "high"
    assert "idle_timeout_ms" not in td


def test_session_update_applies_model_and_voice_overrides(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    overrides = RealtimeSessionOverrides(model="gpt-realtime-1.5", voice="cedar")
    session_update = build_session_update(restaurant, caller_phone="+390000000000", overrides=overrides)
    session = session_update["session"]
    assert session["model"] == "gpt-realtime-1.5"
    assert session["audio"]["output"]["voice"] == "cedar"


def test_session_update_uses_saved_restaurant_config_for_live_calls(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.openai_prompt_override = "Prompt live personalizzato"
    restaurant.openai_realtime_settings = {
        "model": "gpt-realtime-1.5",
        "voice": "cedar",
        "max_response_output_tokens": 180,
        "noise_reduction_type": "far_field",
    }
    db_session.add(restaurant)
    db_session.commit()
    db_session.refresh(restaurant)

    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    session = session_update["session"]

    assert session["instructions"] == "Prompt live personalizzato"
    assert session["model"] == "gpt-realtime-1.5"
    assert session["audio"]["output"]["voice"] == "cedar"
    assert "max_response_output_tokens" not in session
    assert session["audio"]["input"]["noise_reduction"]["type"] == "far_field"


def test_session_update_text_only_mode(db_session):
    """Text-only mode should not set voice or g711 output."""
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(
        restaurant, caller_phone="+390000000000", output_modalities=("text",)
    )
    session = session_update["session"]
    assert "modalities" not in session
    assert "output" not in session["audio"]
    assert "voice" not in session


def test_session_update_noise_reduction(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    assert session_update["session"]["audio"]["input"]["noise_reduction"]["type"] == "far_field"

    overrides = RealtimeSessionOverrides(noise_reduction_type="off")
    session_update = build_session_update(restaurant, caller_phone="+390000000000", overrides=overrides)
    assert "noise_reduction" not in session_update["session"]["audio"]["input"]


def test_session_update_applies_explicit_input_language_override(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    overrides = RealtimeSessionOverrides(input_language="en")
    session_update = build_session_update(restaurant, caller_phone="+390000000000", overrides=overrides)
    assert session_update["session"]["audio"]["input"]["transcription"]["language"] == "en"


def test_transcription_prompt_does_not_contain_restaurant_data(db_session):
    """Transcription prompt must NOT include restaurant name/address to prevent
    Whisper echo-back where the prompt text leaks into transcription output."""
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    transcription_config = session_update["session"]["audio"]["input"]["transcription"]
    prompt = transcription_config.get("prompt", "")
    # Must not contain restaurant name or address
    assert restaurant.name not in prompt, "Transcription prompt must not contain restaurant name"
    assert restaurant.address not in prompt, "Transcription prompt must not contain restaurant address"


def test_runtime_context_message_contains_volatile_call_data(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    message = _runtime_context_message(restaurant, caller_phone="+390000000000")
    assert "Numero chiamante: +390000000000" in message
    assert "Data locale:" in message
    assert "Ora locale:" in message


def test_instructions_contain_anti_hallucination_rules(db_session):
    """System instructions must contain critical anti-hallucination guardrails."""
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    instructions = session_update["session"]["instructions"]
    assert "MAI INVENTARE DATI" in instructions
    assert "ASPETTA L'INTENTO DEL CLIENTE" in instructions


def test_instructions_pin_italian_intonation_and_confirmation_rules(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    instructions = session_update["session"]["instructions"]
    assert "intonazione italiana naturale" in instructions
    assert "Se hai già chiesto la conferma una volta e ancora non è chiara" in instructions
    assert "scandiscili elemento per elemento" in instructions
    assert "non tradurlo e non accorciarlo" in instructions
    assert "Data attuale:" not in instructions
    assert "Ora attuale:" not in instructions


def test_instructions_remove_language_conflict_and_phone_rule_duplication(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    instructions = build_session_update(restaurant, caller_phone="+390000000000")["session"]["instructions"]

    assert instructions.count("Non chiedere mai il numero di telefono.") == 1
    assert "Se un nome proprio è straniero o non italiano, resta in italiano." not in instructions


def test_create_booking_allows_same_caller_when_not_same_day_and_time(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    existing_date = date.fromisoformat(_next_open_date())
    existing_booking, error = create_booking(
        db_session,
        payload=BookingCreate(
            restaurant_id=restaurant.id,
            date=existing_date,
            time=time.fromisoformat("19:00:00"),
            party_size=2,
            customer_name="Cliente Esistente",
            customer_phone="+393339876543",
            source=BookingSource.ai_phone,
            status=BookingStatus.confirmed,
        ),
        changed_by="test",
    )
    assert error is None
    assert existing_booking is not None

    booking_date = _next_open_date_after(existing_date)
    booking_time = "20:00:00"

    state = RealtimeCallState(
        caller_phone="+393339876543",
        twilio_call_sid="CA_same_caller_new_slot",
    )
    _ingest_assistant_transcript(
        state,
        f"{booking_date} alle {booking_time} per 2 persone a nome Luca. Confermo?",
    )
    _ingest_user_transcript(state, "Sì, confermo")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": booking_date,
            "time": booking_time,
            "party_size": 2,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is True


def test_instructions_recover_from_garbled_phone_audio_and_preserve_full_names(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    instructions = session_update["session"]["instructions"]

    assert "DX" in instructions
    assert "casi persone" in instructions
    assert "non trattarla come dato valido" in instructions
    assert "Juan Manuel" in instructions
    assert "non accorciare" in instructions
    assert "ultima risorsa" in instructions
    assert "Non trasferire" in instructions
    assert "rispondi SEMPRE nella stessa lingua del cliente" in instructions
    assert "passa subito a quella lingua" in instructions
    assert "cambia SOLO la lingua della risposta" in instructions
    assert "non cambiare il flusso" in instructions
    assert "Non trasferire solo perché non sta parlando italiano" in instructions


def test_realtime_tools_disallow_extra_fields_without_unsupported_strict_flag():
    tools = build_realtime_tools()
    assert tools
    for tool in tools:
        assert "strict" not in tool
        assert tool["parameters"]["additionalProperties"] is False


def test_instructions_accept_natural_confirmations_and_close_after_success(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    instructions = session_update["session"]["instructions"]
    assert "perfetto" in instructions
    assert "saluta e chiudi la chiamata" in instructions


def test_instructions_use_soft_confirmation_repair_without_magic_word_prompting(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    session_update = build_session_update(restaurant, caller_phone="+390000000000")
    instructions = session_update["session"]["instructions"]

    assert "Se la conferma è ambigua, chiedi una sola volta in modo naturale e breve." in instructions
    assert "Non dire mai al cliente quali parole esatte deve usare" in instructions
    assert "Non usare formule rigide come" in instructions


class _RecordingSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, payload: str) -> None:
        self.messages.append(__import__("json").loads(payload))


def test_response_create_uses_output_modalities_for_audio():
    ws = _RecordingSocket()
    asyncio.run(_send_response_create(ws, output_modalities=("audio",)))
    message = ws.messages[0]
    assert message["type"] == "response.create"
    response = message["response"]
    assert response["output_modalities"] == ["audio"]
    assert response["audio"]["output"]["format"] == {"type": "audio/pcmu"}
    assert "modalities" not in response


def test_response_create_uses_output_modalities_for_text():
    ws = _RecordingSocket()
    asyncio.run(_send_response_create(ws, output_modalities=("text",)))
    message = ws.messages[0]
    response = message["response"]
    assert response["output_modalities"] == ["text"]
    assert "audio" not in response
    assert "modalities" not in response


def test_append_transcript_line_skips_duplicate_consecutive_lines() -> None:
    state = RealtimeCallState()

    assert _append_transcript_line(state, "Agente", "Controllo subito.") is True
    assert _append_transcript_line(state, "Agente", "Controllo subito.") is False
    assert _append_transcript_line(state, "Cliente", "Va bene.") is True

    assert state.transcript_lines == [
        "Agente: Controllo subito.",
        "Cliente: Va bene.",
    ]


def test_successful_call_outcome_marks_escalation_from_final_phrase() -> None:
    state = RealtimeCallState(
        last_assistant_transcript="Non riesco a completare la prenotazione. La metto in contatto con il ristorante."
    )

    assert _successful_call_outcome(state) == "escalated"


def test_successful_call_outcome_marks_failed_write_attempt_as_tool_error() -> None:
    state = RealtimeCallState(
        tool_events=[
            {
                "tool": "create_booking",
                "arguments": {"date": "2026-04-09"},
                "result": {"success": False, "reason": "Conferma esplicita del cliente mancante."},
            }
        ]
    )

    assert _successful_call_outcome(state) == "tool_error"


def test_create_booking_missing_confirmation_returns_no_retry_guidance(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(
        caller_phone="+393401112233",
        twilio_call_sid="CA_confirm_guidance",
        last_user_transcript="grazie",
        last_assistant_transcript="Domani alle 21 per quattro persone a nome Luca. Confermo?",
    )

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": _next_open_date(),
            "time": "21:00:00",
            "party_size": 4,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is False
    assert result["retry_write"] is False
    assert result["needs_explicit_yes"] is True


def test_missing_confirmation_escalates_on_repeated_same_transcript(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    booking_args = {
        "date": _next_open_date(),
        "time": "21:00:00",
        "party_size": 4,
        "customer_name": "Luca",
    }
    state = RealtimeCallState(
        caller_phone="+393401112233",
        twilio_call_sid="CA_confirm_repeat",
        last_user_transcript="grazie",
        last_assistant_transcript="Domani alle 21 per quattro persone a nome Luca. Confermo?",
    )

    first = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments=booking_args,
    )
    second = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments=booking_args,
    )

    assert first["should_escalate"] is False
    assert second["should_escalate"] is True


def test_duplicate_booking_tool_prefers_self_service_over_forced_escalation(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    existing_date = date.fromisoformat(_next_open_date())
    existing, error = create_booking(
        db_session,
        payload=BookingCreate(
            restaurant_id=restaurant.id,
            date=existing_date,
            time=time.fromisoformat("20:00:00"),
            party_size=2,
            customer_name="Cliente Esistente",
            customer_phone="+393339876543",
            source=BookingSource.ai_phone,
            status=BookingStatus.confirmed,
        ),
        changed_by="test",
    )
    assert error is None
    assert existing is not None

    state = RealtimeCallState(
        caller_phone="+393339876543",
        twilio_call_sid="CA_duplicate_self_service",
    )
    _ingest_assistant_transcript(
        state,
        f"{existing.date.isoformat()} alle {existing.time.isoformat()} per {existing.party_size} persone. Confermo?",
    )
    _ingest_user_transcript(state, "Sì, confermo")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": existing.date.isoformat(),
            "time": existing.time.isoformat(),
            "party_size": existing.party_size,
            "customer_name": "Nuovo Nome",
        },
    )

    assert result["success"] is False
    assert result["duplicate_booking"]["confirmation_code"] == existing.confirmation_code
    assert result["should_escalate"] is False
    assert result["can_self_service"] is True
    assert "modific" in result["assistant_instruction"].lower()
    assert "cancell" in result["assistant_instruction"].lower()


def test_tool_scope_update_is_partial_and_keeps_runtime_tool_choice():
    overrides = RealtimeSessionOverrides(tool_choice="required")
    session_update = _build_tool_scope_update(
        tool_names=("check_availability", "escalate_to_human"),
        overrides=overrides,
    )

    assert session_update["type"] == "session.update"
    assert session_update["session"]["tool_choice"] == "required"
    assert [tool["name"] for tool in session_update["session"]["tools"]] == [
        "check_availability",
        "escalate_to_human",
    ]
    assert "instructions" not in session_update["session"]
    assert "audio" not in session_update["session"]
    assert "model" not in session_update["session"]


def test_buffer_twilio_media_payload_keeps_caller_audio_even_during_assistant_speech():
    state = RealtimeCallState(assistant_is_speaking=True, initial_greeting_in_progress=False)
    buffered_audio = bytearray()
    payload = base64.b64encode(b"caller-audio").decode("ascii")

    buffered_packets = _buffer_twilio_media_payload(
        state,
        payload=payload,
        buffered_audio=buffered_audio,
        buffered_packets=0,
    )

    assert buffered_packets == 1
    assert bytes(buffered_audio) == b"caller-audio"
    assert state.dropped_input_audio_packets == 0


def test_buffer_twilio_media_payload_allows_audio_during_initial_greeting_for_barge_in():
    state = RealtimeCallState(assistant_is_speaking=True)
    buffered_audio = bytearray()
    payload = base64.b64encode(b"caller-audio").decode("ascii")

    buffered_packets = _buffer_twilio_media_payload(
        state,
        payload=payload,
        buffered_audio=buffered_audio,
        buffered_packets=0,
    )

    assert buffered_packets == 1
    assert bytes(buffered_audio) == b"caller-audio"
    assert state.dropped_input_audio_packets == 0


def test_finish_initial_greeting_leaves_audio_open_without_grace_gate():
    state = RealtimeCallState(assistant_is_speaking=True)
    _finish_initial_greeting(state)

    assert state.initial_greeting_in_progress is False
    assert state.initial_greeting_grace_until is None

    immediate_buffer = bytearray()
    payload = base64.b64encode(b"echo").decode("ascii")
    assert (
        _buffer_twilio_media_payload(
            state,
            payload=payload,
            buffered_audio=immediate_buffer,
            buffered_packets=0,
        )
        == 1
    )
    assert state.dropped_input_audio_packets == 0
    assert bytes(immediate_buffer) == b"echo"


def test_silent_response_retry_allowed_only_for_true_silent_greeting_or_tool_followup():
    state = RealtimeCallState()

    assert _silent_response_retry_allowed(state, initial_response_phase=True) is True

    state.caller_speech_detected = True
    assert _silent_response_retry_allowed(state, initial_response_phase=True) is False

    state = RealtimeCallState(initial_greeting_in_progress=False)
    assert _silent_response_retry_allowed(state, initial_response_phase=False) is False

    state.pending_tool_followup = True
    assert _silent_response_retry_allowed(state, initial_response_phase=False) is True


def test_tool_scope_update_keeps_realtime_session_type():
    payload = _build_tool_scope_update(
        tool_names=("check_availability", "find_booking"),
        overrides=RealtimeSessionOverrides(),
    )

    assert payload["type"] == "session.update"
    assert payload["session"]["type"] == "realtime"
    assert payload["session"]["tool_choice"] == "auto"
    assert len(payload["session"]["tools"]) == 2


def test_conversation_summary_prompt_anchors_tool_outcomes():
    prompt = _build_conversation_summary_prompt(
        turns=[
            {"role": "user", "text": "Vorrei prenotare un tavolo per sabato alle 20."},
            {"role": "assistant", "text": "Controllo subito."},
            {
                "role": "system",
                "text": (
                    "TOOL create_booking | success=false | reason=Risulta già una prenotazione attiva "
                    "da questo numero nello stesso giorno e orario."
                ),
            },
        ]
    )

    assert "NON dichiarare una prenotazione confermata" in prompt
    assert "I turni di sistema TOOL sono fatti autorevoli" in prompt
    assert "Le trascrizioni possono contenere errori" in prompt
    assert "success=false" in prompt


def test_confirmation_survives_assistant_filler_between_user_yes_and_tool_call():
    """Regression for the real-call bug where a filler assistant utterance
    emitted alongside the create_booking tool call (e.g. "Un momento.")
    overwrote last_assistant_transcript and erased the confirmation cue from
    the previous confirmation question, causing _write_confirmation_granted
    to falsely reject an explicit "Va bene" from the customer.
    """
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_filler_regression",
    )

    # Assistant asks for explicit confirmation.
    _ingest_assistant_transcript(
        state, "Ho bisogno di un sì chiaro per procedere, va bene?"
    )
    assert state.awaiting_confirmation is True

    # Customer confirms clearly.
    _ingest_user_transcript(state, "Va bene")
    assert state.confirmation_granted is True

    # Model emits a short filler utterance right before the tool call.
    _ingest_assistant_transcript(state, "Un momento.")

    # The filler must NOT clear the confirmation — the tool call should pass.
    assert state.awaiting_confirmation is True
    assert state.confirmation_granted is True
    assert _write_confirmation_granted(state) is True


def test_confirmation_not_granted_on_garbled_user_response():
    """Negative regression: a non-affirmative, garbled user turn ("Domi?")
    must not be treated as a confirmation even when the prior assistant turn
    asked for one.
    """
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_garbled_response",
    )
    _ingest_assistant_transcript(
        state,
        "Prenoto per martedì 14 alle 20 per 4 persone a nome Anna, conferma?",
    )
    assert state.awaiting_confirmation is True

    _ingest_user_transcript(state, "Domi?")

    assert state.confirmation_granted is False
    assert _write_confirmation_granted(state) is False


def test_confirmation_granted_on_natural_affirmative_perfetto():
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_natural_affirmative",
    )
    _ingest_assistant_transcript(
        state,
        "Prenoto per sabato alle 21 per 4 persone a nome Juan, conferma?",
    )

    _ingest_user_transcript(state, "Perfetto.")

    assert state.confirmation_granted is True
    assert _write_confirmation_granted(state) is True


def test_confirmation_granted_on_natural_affirmative_accetta():
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_natural_affirmative_accetta",
    )
    _ingest_assistant_transcript(
        state,
        "Perfetto, allora la prenoto per domani alle 21 per cinque persone a nome Juan Manuel. Procedo?",
    )

    _ingest_user_transcript(state, "Accetta")

    assert state.confirmation_granted is True
    assert _write_confirmation_granted(state) is True


def test_confirmation_granted_from_transcription_delta_before_completion():
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_delta_confirmation",
    )
    _ingest_assistant_transcript(
        state,
        "Mi serve un sì chiaro per procedere, va bene?",
    )

    _ingest_input_audio_transcription_delta(state, item_id="item-user-1", delta="S")
    assert state.confirmation_granted is False

    _ingest_input_audio_transcription_delta(state, item_id="item-user-1", delta="ì.")

    assert state.confirmation_granted is True
    assert _write_confirmation_granted(state) is True


def test_name_confirmation_does_not_unlock_booking_write():
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_name_confirmation_scope",
    )

    _ingest_assistant_transcript(state, "Juan Manuel Fuentes, corretto cosi?")

    assert state.last_requested_field == "customer_name"
    assert state.pending_confirmation_kind == "name"
    assert state.awaiting_confirmation is False

    _ingest_user_transcript(state, "Correcto.")

    assert state.confirmation_granted is False
    assert _write_confirmation_granted(state) is False


def test_booking_confirmation_still_works_after_name_confirmation():
    state = RealtimeCallState(
        caller_phone="+41779802809",
        twilio_call_sid="CA_name_then_booking_confirmation",
    )

    _ingest_assistant_transcript(state, "Juan Manuel Fuentes, corretto cosi?")
    _ingest_user_transcript(state, "Correcto.")
    assert _write_confirmation_granted(state) is False

    _ingest_assistant_transcript(
        state,
        "Perfetto, la prenoto per sabato alle 19 per cinque persone a nome Juan Manuel Fuentes. Confermo?",
    )
    _ingest_user_transcript(state, "Sì")

    assert state.pending_confirmation_kind == "write"
    assert state.confirmation_granted is True
    assert _write_confirmation_granted(state) is True


def test_create_booking_success_sets_terminal_write_success(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    booking_date = _next_open_date()
    state = RealtimeCallState(
        caller_phone="+393409991112",
        twilio_call_sid="CA_terminal_write_success",
    )
    _ingest_assistant_transcript(
        state, "5 aprile alle 20:00 per 2 persone a nome Luca. Confermo?"
    )
    _ingest_user_transcript(state, "Sì, confermo")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": booking_date,
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Luca",
        },
    )

    assert result["success"] is True
    assert state.terminal_write_success is True
    assert state.end_call_after_response is True
    assert _should_ignore_post_write_user_turn(state) is True


def test_sync_call_update_merges_extra_data(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    realtime_call = restaurant.call_logs[0]
    realtime_call.twilio_call_sid = "CA_merge_extra_data"
    realtime_call.extra_data = {"twilio_stream_event": "stream-started", "twilio_stream_sid": "MZ123"}
    db_session.add(realtime_call)
    db_session.commit()

    _sync_call_update(
        session_factory,
        call_sid="CA_merge_extra_data",
        fields={
            "summary": "Prenotazione completata.",
            "extra_data": {"openai_session_id": "sess_123", "tool_events": []},
        },
    )

    db_session.refresh(realtime_call)
    assert realtime_call.summary == "Prenotazione completata."
    assert realtime_call.extra_data["twilio_stream_event"] == "stream-started"
    assert realtime_call.extra_data["twilio_stream_sid"] == "MZ123"
    assert realtime_call.extra_data["openai_session_id"] == "sess_123"
    assert realtime_call.extra_data["tool_events"] == []


def test_sync_end_twilio_call_uses_hangup_twiml(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.escalation_phone = "+390201234567"

    with patch("app.services.openai_realtime.settings") as mock_settings:
        mock_settings.twilio_account_sid = "AC123"
        mock_settings.twilio_auth_token = "token123"
        with patch("app.services.openai_realtime.httpx.post") as mock_post:
            mock_post.return_value.is_success = True

            result = _sync_end_twilio_call(restaurant=restaurant, call_sid="CA123")

    assert result is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Calls/CA123.json"
    assert kwargs["auth"] == ("AC123", "token123")
    assert kwargs["data"] == {"Twiml": "<Response><Hangup/></Response>"}
    assert kwargs["timeout"] == 10.0


def test_escalate_to_human_is_simulated_inside_studio(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(
        caller_phone="+393401112233",
        twilio_call_sid="studio-sim",
    )

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="escalate_to_human",
        arguments={"reason": "gruppo grande"},
    )

    assert result["success"] is True
    assert result["transferred"] is True
    assert result["simulated"] is True
