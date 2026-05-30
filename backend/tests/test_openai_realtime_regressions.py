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
    _current_tool_scope,
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

    assert "Greeting Discipline" in prompt
    assert 'Usa "Buongiorno" o "Buonasera" solo nel primo turno della chiamata.' in prompt
    # The old verbose-bridge example was removed in favor of a tighter "single question" rule
    # to prevent the triple-question pattern observed on a real call.
    assert 'fai UNA SOLA domanda breve che raccolga i dati mancanti' in prompt
    assert 'Per che giorno, ora e quante persone?' in prompt
    # And the old write-tool preamble was replaced by an explicit "no preamble" rule for write tools.
    assert "NON usare un preambolo vocale" in prompt
    assert 'NON dire "Un momento", "Procedo", "Controllo" prima di uno strumento di scrittura' in prompt
    assert "Dopo una risposta informativa completa, fai una sola breve apertura naturale" in prompt
    assert "Se vuole, posso anche aiutarla con una prenotazione." in prompt
    assert "Se il cliente non aggiunge altro o resta in silenzio, chiudi con cortesia." in prompt


def test_stored_prompt_repeated_greeting_rule_is_neutralized(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.openai_prompt_override = (
        "Role & Objective\n- Test.\n\n"
        "Personality & Tone\n"
        "- Parla in italiano naturale, caldo, conciso e orientato all'azione. "
        "Inizia la frase con Buongiorno, o Buonasera, in base all'orario.\n"
    )
    db_session.add(restaurant)
    db_session.commit()

    prompt = build_realtime_instructions(restaurant, caller_phone="+393401112233")

    assert "Inizia la frase con Buongiorno" not in prompt
    assert "Greeting Discipline" in prompt
    assert 'non iniziare più le risposte con "Buongiorno"' in prompt


def test_stored_prompt_create_booking_confirmation_rule_is_neutralized(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.openai_prompt_override = (
        "Tools\n"
        "- Strumenti di scrittura: create_booking, modify_booking, cancel_booking.\n"
        "- Usa gli strumenti di scrittura solo dopo una conferma esplicita del cliente\n"
        " e solo nel turno successivo alla domanda finale di conferma.\n\n"
        "Write Action Rules\n"
        "- Prima di create_booking, modify_booking o cancel_booking: "
        "riassumi i dettagli in una frase e chiedi conferma.\n"
        "- Esegui il tool solo nel turno successivo a una conferma chiara del cliente.\n"
    )
    db_session.add(restaurant)
    db_session.commit()

    prompt = build_realtime_instructions(restaurant, caller_phone="+393401112233")

    assert "Create Booking Discipline" in prompt
    assert "dopo che il cliente fornisce il nome,\n  esegui subito create_booking" in prompt
    assert "Prima di create_booking, modify_booking o cancel_booking" not in prompt
    assert "solo dopo una conferma esplicita del cliente" not in prompt


def test_prompt_diagnostics_warn_when_prompt_repeats_greetings(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    prompt = (
        "Role & Objective\n- Test.\n\n"
        "Personality & Tone\n"
        "- Parla in italiano naturale. Inizia la frase con Buongiorno, o Buonasera, in base all'orario.\n\n"
        "Language\n- Segui la lingua del cliente.\n\n"
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

    greeting = next(item for item in diagnostics if item["label"] == "Greeting discipline")
    assert greeting["status"] == "warn"


def test_prompt_diagnostics_warn_when_create_booking_waits_for_extra_confirmation(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    prompt = (
        "Role & Objective\n- Test.\n\n"
        "Personality & Tone\n- Non ripetere.\n\n"
        "Language\n- Segui la lingua del cliente.\n\n"
        "Tools\n"
        "- Controllo subito.\n"
        "- Strumenti di scrittura: create_booking, modify_booking, cancel_booking.\n"
        "- Usa gli strumenti di scrittura solo dopo una conferma esplicita del cliente\n"
        " e solo nel turno successivo alla domanda finale di conferma.\n\n"
        "Write Action Rules\n- Conferma esplicita per create, modify e cancel.\n\n"
        "Safety & Escalation\n- La metto in contatto con il ristorante.\n\n"
        "Unclear Audio\n- Non inventare."
    )

    diagnostics = studio_prompt_diagnostics(
        prompt,
        restaurant=restaurant,
        effective_overrides=RealtimeSessionOverrides(),
    )

    create_flow = next(item for item in diagnostics if item["label"] == "Create booking flow")
    assert create_flow["status"] == "warn"


def test_stored_prompt_context_is_refreshed_from_restaurant_record(db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.opening_hours = {"lunch": "12:00-16:00", "dinner": "19:00-23:30"}
    restaurant.turni = [
        {"name": "Pranzo 1", "start": "12:00", "end": "14:00", "max_covers": 40},
        {"name": "Pranzo 2", "start": "14:00", "end": "16:00", "max_covers": 40},
    ]
    restaurant.weekly_closures = []
    restaurant.openai_prompt_override = (
        "Context\n"
        "- Ristorante: Old Name\n"
        "- Indirizzo: Old Address\n"
        "- Timezone: UTC\n"
        '- Orari: {"lunch": "12:00-15:00"}\n'
        '- Turni: [{"name": "Old", "max_covers": 10}]\n'
        '- Chiusure settimanali: ["monday"]\n'
        "- Chiusure straordinarie: []\n"
        "- Soglia grandi gruppi: 99"
    )
    db_session.add(restaurant)
    db_session.commit()

    prompt = build_realtime_instructions(restaurant, caller_phone="+393401112233")

    assert "- Ristorante: Trattoria da Mario" in prompt
    assert "- Indirizzo: Via Roma 42, 20121 Milano" in prompt
    assert "- Timezone: Europe/Rome" in prompt
    assert '- Orari: {"lunch": "12:00-16:00", "dinner": "19:00-23:30"}' in prompt
    assert '"max_covers": 40' in prompt
    assert '- Chiusure settimanali: []' in prompt
    assert "- Soglia grandi gruppi: 8" in prompt


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


def test_check_availability_uses_model_arguments_directly(db_session):
    """Verify that check_availability passes the model's arguments through
    without server-side normalization overrides."""
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_direct_args")

    # Even if transcript mentions children, the model's party_size is used as-is.
    _ingest_user_transcript(state, "Siamo quattro con tre bambini.")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="check_availability",
        arguments={
            "date": _next_open_date(),
            "party_size": 7,
            "time": "21:00:00",
        },
    )

    assert result["available"] is True
    # The model is expected to send the correct total (including children)
    # as instructed by the prompt — no server-side override.
    assert result["slot"]["turno"] == "secondo"


def test_check_availability_respects_model_time_preference(db_session):
    """Verify that the model's time_preference is used directly, not overwritten
    by transcript-derived context."""
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_time_direct")
    _ingest_user_transcript(state, "Domani ore 12, tre persone.")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="check_availability",
        arguments={
            "date": _next_open_date(),
            "party_size": 3,
            "time": "21:00:00",
        },
    )

    assert result["available"] is True
    # The model sent 21:00 — that is used directly, even though
    # the transcript mentioned "ore 12".
    assert result["slot"]["time"] == "21:00"


def test_create_booking_is_blocked_when_time_outside_turni(db_session):
    """Verify that real data guards (availability re-check) still prevent
    invalid bookings even without the intent-based guard."""
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    state = RealtimeCallState(caller_phone="+393409991111", twilio_call_sid="CA_time_guard")

    _ingest_user_transcript(state, "Vorrei prenotare per le 17.")

    result = _sync_dispatch_tool(
        session_factory,
        restaurant=restaurant,
        state=state,
        tool_name="create_booking",
        arguments={
            "date": _next_open_date(),
            "time": "17:00:00",
            "party_size": 2,
            "customer_name": "Francesco",
        },
    )

    assert result["success"] is False


def test_successful_create_booking_links_call_log_and_summary_uses_tool_truth(db_session):
    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    booking_date = _next_open_date()
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
    state.tool_events.append(
        {
            "tool": "check_availability",
            "arguments": {"date": booking_date, "party_size": 2, "time": "21:00:00"},
            "result": {"available": True, "slot": {"time": "21:00"}},
        }
    )
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
            "date": booking_date,
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
                "date": booking_date,
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


# ---------------------------------------------------------------------------
# Regression coverage for the 2026-05-29 false-escalation incident.
#
# Three calls escalated that should not have. Root causes:
#  A) A combined opener ("Per che giorno, a che ora e per quante persone?")
#     was tagged as the single field `party_size`, so valid answers to the day
#     and time were scored as failed party-size attempts -> forced escalation
#     before any tool ran.
#  B) Whisper echoed the transcription prompt ("Prenotazione telefonica") as
#     fake caller speech, which was counted as a failed-name attempt.
#  C) Escalation was a one-way trap with no recovery after real progress.
# ---------------------------------------------------------------------------


def _append_successful_availability_reg(
    state: RealtimeCallState,
    *,
    booking_date: str,
    booking_time: str,
    party_size: int,
) -> None:
    state.tool_events.append(
        {
            "tool": "check_availability",
            "arguments": {"date": booking_date, "party_size": party_size, "time": booking_time},
            "result": {"available": True, "slot": {"time": booking_time[:5]}},
        }
    )


def test_combined_opener_is_tagged_as_booking_details_not_party_size():
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_combined_opener")
    _ingest_assistant_transcript(state, "Per che giorno, a che ora e per quante persone?")
    assert state.last_requested_field == "booking_details"


def test_combined_opener_answers_do_not_force_escalation():
    """Call 1 (12:19): caller gave day, time and party in three fragments and
    was wrongly transferred. Those answers must not trip the strike counter."""
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_call1_replay")
    _ingest_assistant_transcript(state, "Per che giorno, a che ora e per quante persone?")

    _ingest_user_transcript(state, "2 giugno.")
    _ingest_user_transcript(state, "Dodici30.")
    _ingest_user_transcript(state, "Per sette persone.")

    assert state.should_escalate is False
    # The agent must still be able to read/write, not be locked to escalate-only.
    assert _current_tool_scope(state) != ("escalate_to_human",)
    # Party size was understood from "sette persone".
    assert state.booking_context.get("party_size") == 7


def test_number_followed_by_persone_is_extracted_as_party_size():
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_party_persone")
    _ingest_assistant_transcript(state, "Per quante persone?")
    _ingest_user_transcript(state, "Per sette persone.")
    assert state.last_user_reply_valid is True
    assert state.booking_context.get("party_size") == 7


def test_transcription_prompt_echo_invalidates_name_but_does_not_strike():
    """Call 2 (12:29): a Whisper echo answered the name question. It must block
    the write (invalid reply) yet must NOT count as a failed-field attempt."""
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_echo_name")
    _ingest_assistant_transcript(state, "Ho disponibilità per oggi alle 20:30. A che nome prenoto?")

    _ingest_user_transcript(state, "Prenotazione telefonica.")

    assert state.last_user_reply_valid is False
    assert state.should_escalate is False
    assert state.invalid_field_attempts.get("customer_name", 0) == 0


def test_call2_echo_then_one_unclear_name_does_not_escalate():
    """Full Call 2 replay: availability succeeded, then an echo and one unclear
    reply ("Mezz'ora?"). One real strike is not enough to force a transfer, and
    create_booking must remain reachable for the recovery turn."""
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_call2_replay")
    _append_successful_availability_reg(
        state, booking_date="2026-05-29", booking_time="20:30:00", party_size=3
    )
    _ingest_assistant_transcript(state, "Ho disponibilità per oggi alle 20:30. A che nome prenoto?")

    _ingest_user_transcript(state, "Prenotazione telefonica.")  # echo -> no strike
    _ingest_user_transcript(state, "Mezz'ora?")  # one genuine unclear reply -> 1 strike

    assert state.should_escalate is False
    assert "create_booking" in _current_tool_scope(state)


def test_two_genuinely_unclear_same_field_answers_still_escalate():
    """Guardrail must still fire for real ambiguity (no false-negative)."""
    state = RealtimeCallState(caller_phone="+393401112233", twilio_call_sid="CA_real_escalation")
    _ingest_assistant_transcript(
        state,
        "Per la cena abbiamo due fasce: dalle 19 alle 21 oppure dalle 21 in poi. Quale preferisce?",
    )
    _ingest_user_transcript(state, "Ciao.")
    _ingest_assistant_transcript(state, "Preferisce dalle 19 o dalle 21?")
    _ingest_user_transcript(state, "Va bene.")
    assert state.should_escalate is True
