from __future__ import annotations

import asyncio
import base64
import json
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
import jwt
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from websockets.asyncio.client import connect

from app.core.config import settings
from app.core.observability import json_log
from app.models import Booking, CallLog, Restaurant
from app.schemas.booking import BookingCreate, BookingUpdate
from app.schemas.common import BookingSource, BookingStatus
from app.schemas.tools import ModifyBookingChanges
from app.services.availability import ACTIVE_STATUSES, check_availability
from app.services.bookings import create_booking, find_bookings_for_caller, update_booking

AFFIRMATIVE_WORDS = {
    "si",
    "sì",
    "certo",
    "confermo",
    "confermata",
    "accetta",
    "accetto",
    "va bene",
    "va benissimo",
    "ok",
    "okay",
    "esatto",
    "perfetto",
    "perfetta",
    "d'accordo",
    "proceda",
    "procedi",
    "faccia pure",
    "vai pure",
}
# Phrases an assistant turn may contain when it is explicitly asking the customer
# to confirm a write (booking, modification, cancellation) or narrating the action
# it is about to perform. Kept as substrings; "conferma" covers "conferma?",
# "confermo", "confermi", "confermato".
CONFIRMATION_CUES = {
    "conferma",
    "confermo",
    "confermi",
    "prenoto",
    "le confermo",
    "procedo",
    "cancello",
    "modifico",
    "va bene?",
    "prenotazione",
}
SUPPORTED_REALTIME_MODELS = {"gpt-realtime", "gpt-realtime-1.5", "gpt-realtime-mini"}
SUPPORTED_REALTIME_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "cedar",
    "coral",
    "echo",
    "marin",
    "sage",
    "shimmer",
    "verse",
}
RECOMMENDED_REALTIME_VOICES = {"marin", "cedar"}
READ_ONLY_TOOL_NAMES = ("check_availability", "find_booking", "escalate_to_human")
FULL_TOOL_NAMES = (
    "check_availability",
    "find_booking",
    "create_booking",
    "modify_booking",
    "cancel_booking",
    "escalate_to_human",
)
INPUT_AUDIO_BUFFER_PACKET_THRESHOLD = 5
SILENT_RESPONSE_WATCHDOG_SECONDS = 1.8
MAX_SILENT_RESPONSE_RETRIES = 1
SUMMARY_TRIGGER_TURNS = 10
SUMMARY_KEEP_LAST_TURNS = 4
SUMMARY_MODEL = "gpt-4o-mini"
SUPPORTED_RUNTIME_OVERRIDE_FIELDS = {
    "model",
    "voice",
    "tool_choice",
    "turn_detection_type",
    "vad_threshold",
    "vad_prefix_padding_ms",
    "vad_silence_duration_ms",
    "vad_idle_timeout_ms",
    "semantic_vad_eagerness",
    "interrupt_response",
    "create_response",
    "noise_reduction_type",
    "transcription_model",
    "input_language",
    "tracing_enabled",
    "truncation_mode",
    "truncation_retention_ratio",
}
PRACTICAL_STUDIO_FIELDS = {
    "model",
    "voice",
    "turn_detection_type",
    "vad_threshold",
    "vad_silence_duration_ms",
    "vad_idle_timeout_ms",
    "noise_reduction_type",
    "input_language",
    "tracing_enabled",
    "truncation_mode",
    "truncation_retention_ratio",
}
STUDIO_PRESETS = [
    {
        "id": "balanced",
        "label": "Balanced",
        "description": (
            "Recommended default for phone bookings: stable turn detection, "
            "traceability, and concise replies."
        ),
        "session_overrides": {
            "model": "gpt-realtime-1.5",
            "voice": "cedar",
            "tool_choice": "auto",
            "turn_detection_type": "server_vad",
            "vad_threshold": 0.58,
            "vad_silence_duration_ms": 900,
            "vad_idle_timeout_ms": 7000,
            "noise_reduction_type": "far_field",
            "tracing_enabled": True,
            "truncation_mode": "retention_ratio",
            "truncation_retention_ratio": 0.75,
        },
    },
    {
        "id": "noisy_room",
        "label": "Noisy room",
        "description": (
            "For busy dining rooms and speakerphone use. Slightly more patient "
            "turn-taking and stronger noise handling."
        ),
        "session_overrides": {
            "model": "gpt-realtime-1.5",
            "voice": "cedar",
            "tool_choice": "auto",
            "turn_detection_type": "server_vad",
            "vad_threshold": 0.62,
            "vad_silence_duration_ms": 1100,
            "vad_idle_timeout_ms": 8000,
            "noise_reduction_type": "far_field",
            "tracing_enabled": True,
            "truncation_mode": "retention_ratio",
            "truncation_retention_ratio": 0.72,
        },
    },
]
STUDIO_SCENARIOS = [
    {
        "id": "new_booking",
        "label": "New booking",
        "message": "Vorrei prenotare un tavolo per domani sera alle 20 per due persone.",
        "goal": "Should confirm intent, collect only missing data, and verify availability before writing.",
    },
    {
        "id": "modify_booking",
        "label": "Modify booking",
        "message": "Vorrei spostare la mia prenotazione di domani dalle 20 alle 21.",
        "goal": "Should find the booking first, then re-check availability before modifying.",
    },
    {
        "id": "cancel_booking",
        "label": "Cancel booking",
        "message": "Vorrei cancellare la mia prenotazione per venerdì.",
        "goal": "Should identify the booking, ask for confirmation, and cancel only after a separate yes.",
    },
    {
        "id": "info_request",
        "label": "Info request",
        "message": "Siete aperti lunedì a pranzo e dove siete esattamente?",
        "goal": "Should answer from context only, without forcing a booking flow.",
    },
    {
        "id": "unclear_audio",
        "label": "Unclear caller",
        "message": "Pronto? Mi sente? Vorrei per sabato... cioè forse domenica... non so.",
        "goal": "Should clarify only the missing part, not guess, and stay concise.",
    },
    {
        "id": "human_handoff",
        "label": "Escalation",
        "message": "Siamo in dodici con allergie importanti, preferisco parlare con il ristorante.",
        "goal": "Should use the escape hatch quickly instead of over-handling a risky case.",
    },
]
PROMPT_SECTIONS = [
    "Role & Objective",
    "Personality & Tone",
    "Language",
    "Context",
    "CRITICAL RULES",
    "Tools",
    "Conversation Flow",
    "Write Action Rules",
    "Duplicate Prevention",
    "Safety & Escalation",
    "Unclear Audio",
]
OVERRIDE_FIELD_LABELS = {
    "model": "Model",
    "voice": "Voice",
    "tool_choice": "Tool choice",
    "temperature": "Temperature",
    "speed": "Speed",
    "max_response_output_tokens": "Max output tokens",
    "turn_detection_type": "Turn detection type",
    "vad_threshold": "VAD threshold",
    "vad_prefix_padding_ms": "Prefix padding ms",
    "vad_silence_duration_ms": "Silence duration ms",
    "vad_idle_timeout_ms": "Idle timeout ms",
    "semantic_vad_eagerness": "Semantic VAD eagerness",
    "interrupt_response": "Interrupt response",
    "create_response": "Create response",
    "noise_reduction_type": "Noise reduction",
    "transcription_model": "Transcription model",
    "input_language": "Input language",
    "tracing_enabled": "Tracing",
    "truncation_mode": "Truncation mode",
    "truncation_retention_ratio": "Retention ratio",
    "truncation_post_instructions_tokens": "Post-instructions tokens",
}


@dataclass(slots=True)
class RealtimeSessionOverrides:
    model: str | None = None
    voice: str | None = None
    tool_choice: Literal["auto", "none", "required"] = "auto"
    temperature: float = 0.8
    speed: float = 0.95
    max_response_output_tokens: int = 300
    turn_detection_type: Literal["server_vad", "semantic_vad"] = "server_vad"
    vad_threshold: float = 0.58
    vad_prefix_padding_ms: int = 300
    vad_silence_duration_ms: int = 900
    vad_idle_timeout_ms: int = 7000
    semantic_vad_eagerness: Literal["low", "medium", "high", "auto"] = "medium"
    interrupt_response: bool = True
    create_response: bool = True
    noise_reduction_type: Literal["near_field", "far_field", "off"] = "far_field"
    transcription_model: str = "gpt-4o-mini-transcribe"
    input_language: str | None = None
    tracing_enabled: bool = True
    truncation_mode: Literal["retention_ratio", "disabled"] = "retention_ratio"
    truncation_retention_ratio: float = 0.75
    truncation_post_instructions_tokens: int = 1800


@dataclass(slots=True)
class RealtimeCallState:
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stream_sid: str | None = None
    openai_session_id: str | None = None
    last_user_transcript: str = ""
    last_assistant_transcript: str = ""
    transcript_lines: list[str] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    outcome: str = "info_provided"
    call_status: str = "unknown"
    caller_phone: str = ""
    twilio_call_sid: str = ""
    technical_tool_failures: int = 0
    response_in_progress: bool = False
    last_audio_item_id: str | None = None
    last_audio_content_index: int = 0
    last_audio_bytes_sent: int = 0
    last_response_usage: dict[str, Any] | None = None
    transcription_events: list[dict[str, Any]] = field(default_factory=list)
    pending_assistant_audio_transcript: str = ""
    pending_tool_followup: bool = False
    missing_confirmation_failures: int = 0
    confirmation_guard_transcript: str = ""
    awaiting_confirmation: bool = False
    confirmation_granted: bool = False
    pending_user_audio_transcripts: dict[str, str] = field(default_factory=dict)
    end_call_after_response: bool = False
    assistant_is_speaking: bool = False
    response_watchdog_generation: int = 0
    response_audio_started: bool = False
    silent_response_retries: int = 0
    dropped_input_audio_packets: int = 0
    initial_greeting_in_progress: bool = True
    initial_greeting_grace_until: datetime | None = None
    conversation_turns: list[dict[str, str]] = field(default_factory=list)
    conversation_item_ids: list[str] = field(default_factory=list)
    latest_summary: str | None = None


def default_session_overrides() -> RealtimeSessionOverrides:
    return RealtimeSessionOverrides(
        model=settings.openai_realtime_model,
        voice=settings.openai_realtime_voice,
    )


def _override_values(overrides: RealtimeSessionOverrides) -> dict[str, Any]:
    return {
        key: getattr(overrides, key)
        for key in RealtimeSessionOverrides.__dataclass_fields__.keys()
        if getattr(overrides, key) is not None
    }


def _format_override_value(value: Any) -> str:
    if value is None:
        return "default"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def restaurant_session_overrides(restaurant: Restaurant) -> RealtimeSessionOverrides:
    raw = restaurant.openai_realtime_settings or {}
    allowed_keys = SUPPORTED_RUNTIME_OVERRIDE_FIELDS
    cleaned = {key: value for key, value in raw.items() if key in allowed_keys and value is not None}
    return replace(default_session_overrides(), **cleaned)


def merged_session_overrides(
    restaurant: Restaurant,
    overrides: RealtimeSessionOverrides | None = None,
) -> RealtimeSessionOverrides:
    base = restaurant_session_overrides(restaurant)
    if overrides is None:
        return base
    return replace(base, **_override_values(overrides))


def realtime_ws_url(model: str | None) -> str:
    selected_model = (model or settings.openai_realtime_model).strip() or settings.openai_realtime_model
    parts = urlsplit(settings.openai_realtime_base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = selected_model
    return urlunsplit(parts._replace(query=urlencode(query)))


def realtime_headers() -> dict[str, str]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY non configurata.")
    return {"Authorization": f"Bearer {settings.openai_api_key}"}


def _restaurant_now_strings(restaurant: Restaurant) -> tuple[str, str, str]:
    local_now = datetime.now(UTC).astimezone(ZoneInfo(restaurant.timezone))
    return (
        local_now.strftime("%Y-%m-%d"),
        local_now.strftime("%H:%M"),
        local_now.strftime("%A"),
    )


def _runtime_context_message(restaurant: Restaurant, *, caller_phone: str) -> str:
    current_date, current_time, current_day = _restaurant_now_strings(restaurant)
    return (
        "Contesto runtime della chiamata. "
        f"Numero chiamante: {caller_phone or 'non disponibile'}. "
        f"Data locale: {current_date}. "
        f"Ora locale: {current_time}. "
        f"Giorno locale: {current_day}. "
        "Usa questi dati come riferimento corrente della chiamata."
    )


def _transcription_prompt(restaurant: Restaurant) -> str:
    # IMPORTANT: Do NOT include restaurant name, address or other contextual data
    # in the transcription prompt. Whisper-family models echo prompt text verbatim
    # when audio is unclear, causing garbage transcriptions that confuse the agent.
    return (
        "Trascrivi in modo naturale nella lingua parlata dal cliente. Priorità assoluta a nomi propri, "
        "numeri di persone, orari, date e sì/no espliciti. Non inventare parole. "
        "Non trasformare rumori, lettere isolate o frammenti senza senso in dati di prenotazione."
    )


def _extract_message_text(output: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in output.get("content", []):
        if item.get("type") in {"text", "output_text"} and item.get("text"):
            texts.append(str(item["text"]).strip())
        if item.get("type") in {"audio", "output_audio"} and item.get("transcript"):
            texts.append(str(item["transcript"]).strip())
    return " ".join(part for part in texts if part).strip()


def _append_transcript_line(state: RealtimeCallState, speaker: str, text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    line = f"{speaker}: {cleaned}"
    if state.transcript_lines and state.transcript_lines[-1] == line:
        return False
    state.transcript_lines.append(line)
    return True


def _record_conversation_turn(
    state: RealtimeCallState,
    *,
    role: Literal["user", "assistant", "system"],
    text: str,
    item_id: str | None = None,
) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    if item_id:
        state.conversation_item_ids.append(item_id)
    state.conversation_turns.append({"role": role, "text": cleaned, "item_id": item_id or ""})


def _recent_conversation_excerpt(state: RealtimeCallState, *, keep_last_turns: int = SUMMARY_KEEP_LAST_TURNS) -> str:
    excerpt = state.conversation_turns[-keep_last_turns:]
    return "\n".join(f"{turn['role']}: {turn['text']}" for turn in excerpt if turn.get("text"))


def _format_tool_event_for_summary(tool_name: str, result: dict[str, Any]) -> str:
    details: list[str] = []
    if "success" in result:
        details.append(f"success={str(bool(result.get('success'))).lower()}")
    if "available" in result:
        details.append(f"available={str(bool(result.get('available'))).lower()}")
    if "open" in result:
        details.append(f"open={str(bool(result.get('open'))).lower()}")
    if result.get("technical_error"):
        details.append("technical_error=true")
    if result.get("should_escalate") is True:
        details.append("should_escalate=true")
    reason = str(result.get("reason") or "").strip()
    if reason:
        details.append(f"reason={reason}")
    duplicate = result.get("duplicate_booking") if isinstance(result.get("duplicate_booking"), dict) else None
    if duplicate:
        details.append(
            "duplicate_booking="
            f"{duplicate.get('date')} {duplicate.get('time')} "
            f"({duplicate.get('confirmation_code')})"
        )
    if not details:
        details.append("result=recorded")
    return f"TOOL {tool_name} | " + " | ".join(details)


def _build_conversation_summary_prompt(turns: list[dict[str, str]]) -> str:
    transcript = "\n".join(f"{turn['role']}: {turn['text']}" for turn in turns if turn.get("text"))
    return (
        "Riassumi questa telefonata per mantenere il contesto operativo del ristorante. "
        "Mantieni solo fatti utili: intento, data/orario richiesti, numero persone, nome cliente, "
        "vincoli, conferme ottenute, errori tecnici, decisioni e follow-up. "
        "Scrivi in italiano, massimo 6 righe brevi, senza inventare nulla.\n"
        "- I turni di sistema TOOL sono fatti autorevoli e prevalgono su frasi dell'assistente se c'è conflitto.\n"
        "- Le trascrizioni possono contenere errori: se manca certezza, segnala l'incertezza invece di indovinare.\n"
        "- NON dichiarare una prenotazione confermata se create_booking non ha success=true.\n"
        "- Se un tool di scrittura fallisce, dillo esplicitamente nel riassunto.\n\n"
        f"{transcript}"
    )


def _successful_call_outcome(state: RealtimeCallState) -> str:
    if state.outcome != "info_provided":
        return state.outcome

    assistant_text = state.last_assistant_transcript.lower()
    if "la metto in contatto con il ristorante" in assistant_text:
        return "escalated"

    failed_write_attempt = any(
        event.get("tool") in {"create_booking", "modify_booking", "cancel_booking"}
        and isinstance(event.get("result"), dict)
        and event["result"].get("success") is False
        for event in state.tool_events
    )
    if failed_write_attempt:
        return "tool_error"

    return state.outcome


def _missing_confirmation_result(state: RealtimeCallState) -> dict[str, Any]:
    current_transcript = state.last_user_transcript.strip().lower()
    if current_transcript and current_transcript != state.confirmation_guard_transcript:
        state.confirmation_guard_transcript = current_transcript
        state.missing_confirmation_failures = 1
    else:
        state.missing_confirmation_failures += 1
    return {
        "success": False,
        "reason": "Conferma esplicita del cliente mancante.",
        "needs_explicit_yes": True,
        "retry_write": False,
        "should_escalate": state.missing_confirmation_failures >= 2,
        "assistant_instruction": (
            "Se la conferma è ambigua, chiedi una sola volta in modo naturale e breve. "
            "Se resta ambigua, trasferisci al ristorante."
        ),
        "next_step": (
            "Chiedi una sola conferma finale breve in modo naturale. Se non è ancora chiara, passa a un umano."
            if state.missing_confirmation_failures >= 2
            else "Chiedi una sola conferma finale breve nel turno successivo. Non richiamare subito il tool."
        ),
    }


def build_realtime_instructions(
    restaurant: Restaurant,
    *,
    caller_phone: str,
    prompt_override: str | None = None,
) -> str:
    stored_prompt = (restaurant.openai_prompt_override or "").strip()
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()
    if stored_prompt:
        return stored_prompt

    booking_rules = restaurant.booking_rules or {}
    large_group_threshold = booking_rules.get("large_group_threshold", 8)
    return f"""
Role & Objective
- Sei il receptionist telefonico di {restaurant.name}.
- Gestisci nuove prenotazioni, modifiche, cancellazioni, richieste informative e passaggio a un umano quando serve.
- Obiettivo primario: chiudere la richiesta nel minor numero di turni possibile, con chiarezza e affidabilità.
- Quando la richiesta è completata, chiudi subito.
- Il passaggio al ristorante è una ultima risorsa: usalo solo nei casi esplicitamente previsti sotto.

Personality & Tone
- Parla in italiano naturale, caldo, conciso e orientato all'azione.
- Parla con intonazione italiana naturale, con ritmo melodico e pause espressive tipiche del parlato italiano.
- Massimo due frasi brevi per turno. Se basta una frase, usane una sola.
- Tono: ospitale, elegante, diretto, mai robotico.
- Velocità: rispondi rapidamente ma senza sembrare di fretta.
- Nessun gergo tecnico, nessun riepilogo lungo, nessuna spiegazione di sistema.
- Non aprire ogni risposta con un nuovo saluto o con il nome del ristorante.
- Se un'informazione è già chiara, non richiederla. Se il cliente la ripete, accettala e vai avanti.
- Nomi clienti: preserva il nome completo esatto sentito. Se senti "Juan Manuel", non accorciare a "Manuel".
- Se sei incerto su un nome, chiedi una sola conferma breve del nome completo.
- Se il cliente chiede il tuo nome: "Mi chiamo Edoardo."
- Se chiede se sei un'AI: "Sono l'assistente digitale del ristorante. Mi dica pure."
- Stile: {restaurant.agent_style_notes or "Tono ospitale, elegante e diretto."}
- Varia leggermente le frasi brevi di cortesia e i preamboli, ma non cambiare la struttura del flusso.
- Puoi usare raramente parole naturali come "Ecco" o "Allora" se aiutano il ritmo, ma senza esagerare.

Language
- Se il cliente parla chiaramente un'altra lingua che sai gestire, segui la lingua del cliente.
- Apri in italiano solo come default iniziale quando il chiamante non ha ancora mostrato un'altra lingua.
- Per impostazione predefinita, seguire la lingua del cliente funziona meglio che forzare sempre l'italiano.
- Se cambi lingua, cambia SOLO la lingua della risposta:
  non cambiare il flusso, le regole di conferma, i tool, i criteri di sicurezza o il livello di servizio.
- Non cambiare lingua inutilmente a metà conversazione.
- Se l'audio è poco chiaro, chiedi una sola volta di ripetere lentamente nella lingua che il cliente sta usando.
- Non trasferire solo perché non sta parlando italiano.
- Trasferisci solo se la lingua resta incomprensibile
  o se davvero non riesci a gestire bene la richiesta in quella lingua.

Context
- Ristorante: {restaurant.name}
- Indirizzo: {restaurant.address}
- Timezone: {restaurant.timezone}
- Orari: {json.dumps(restaurant.opening_hours or {{}}, ensure_ascii=False)}
- Turni: {json.dumps(restaurant.turni or [], ensure_ascii=False)}
- Chiusure settimanali: {json.dumps(restaurant.weekly_closures or [], ensure_ascii=False)}
- Chiusure straordinarie: {json.dumps(restaurant.closure_dates or [], ensure_ascii=False)}
- Soglia grandi gruppi: {large_group_threshold}
- Saluto iniziale solo per apertura della chiamata:
  {restaurant.custom_greeting or "Buongiorno, come posso aiutarla?"}

CRITICAL RULES — NEVER VIOLATE
- MAI INVENTARE DATI: disponibilità, dettagli, nomi, date, orari o risultati.
- ASPETTA L'INTENTO DEL CLIENTE. Se è già chiaro, vai subito al punto.
- Se ti manca un dato obbligatorio, chiedi solo il dato mancante.
- Non fare più di una domanda per turno, salvo quando raccogli insieme
  giorno, ora e numero persone all'inizio di una nuova prenotazione.
- Non ripetere la stessa domanda, la stessa conferma o lo stesso riepilogo più di una volta.
- Non chiedere mai il numero di telefono.
- Non dire mai l'anno nelle date.
- Non promettere SMS, WhatsApp o email di conferma.
- Non lasciare la conversazione aperta.
- Non trasferire al ristorante per normali chiarimenti su giorno, orario, numero persone o nome.
- SE UNA TRASCRIZIONE È SENZA SENSO, non trattarla come dato valido.
  Esempi: "DX", "casi persone", lettere isolate, rumori o parole incompatibili con la domanda.

Tools
- Strumenti di lettura: check_availability, find_booking.
- Strumenti di scrittura: create_booking, modify_booking, cancel_booking.
- Usa gli strumenti di lettura in modo proattivo quando servono.
- Usa gli strumenti di scrittura solo dopo una conferma esplicita del cliente
  e solo nel turno successivo alla domanda finale di conferma.
- Prima di un tool di lettura usa al massimo una frase breve: "Controllo subito." oppure "Verifico."
- Prima di un tool di scrittura usa al massimo una frase breve: "Un momento." oppure "Procedo."
- Chiama il tool subito dopo il preambolo.
- Se il tool restituisce retry_write=false o should_escalate=true, non ripeterlo nello stesso turno.
- Se un tool di scrittura riesce, comunica l'esito in una sola frase breve, saluta e chiudi la chiamata.

Conversation Flow
- Se l'intento è già chiaro, vai subito nel flusso corretto. Non chiedere "Come posso aiutarla?" se non serve.
- Se la conversazione è già avviata, rispondi direttamente senza ripetere un saluto iniziale.
- Nuova prenotazione:
  - raccogli giorno, ora e numero persone
  - se manca un dato, chiedi solo quel dato
  - usa check_availability prima di confermare
  - se c'è disponibilità, raccogli il nome
  - fai una sola conferma finale
  - aspetta il turno successivo con un sì esplicito
  - solo allora crea la prenotazione
- Se l'orario non è disponibile, proponi al massimo due alternative concrete e vicine.
- Se il nome non è chiaro dopo due tentativi mirati, passa a un umano.
- Modifica e cancellazione:
  - trova prima la prenotazione
  - se serve distinguere più risultati, chiedi il minimo indispensabile
  - fai una sola conferma finale
  - esegui solo nel turno successivo a un sì esplicito
- Richieste informative:
  - rispondi solo con dati presenti nel contesto
  - se il dato non è nel contesto, dì che non puoi confermarlo con certezza
  - trasferisci solo se il cliente chiede una verifica umana o serve una decisione operativa
  - per domande sul menu rispondi solo:
    "Offriamo cucina tradizionale milanese: risotti, cotoletta,
    ossobuco e altre specialità lombarde."
- Non comunicare mai il codice di conferma.
- Se devi leggere numeri, codici, iniziali o lettere, scandiscili elemento per elemento con piccole pause naturali.
- Per orari e numeri di telefono letti ad alta voce, pronuncia chiaramente cifra per cifra quando serve evitare errori.
- Chiusura:
  - quando la richiesta è risolta, fai una sola frase finale breve
  - non aggiungere altre domande
  - non attendere altro se hai già dato conferma o risposta completa

Phone Rules
- Il numero del chiamante viene fornito dal sistema nel contesto runtime.
- Usa sempre il numero della chiamata come numero di contatto della prenotazione.
- Se il cliente chiede di usare un numero diverso, non prometterlo e passa a un umano.
- Se un nome proprio è straniero o non italiano, non tradurlo e non accorciarlo.
- Ripetilo con la pronuncia più naturale possibile senza cambiare il comportamento del servizio.

Write Action Rules
- Per create_booking, modify_booking e cancel_booking serve sempre un sì esplicito del cliente.
- Non eseguire azioni di scrittura nello stesso turno in cui fai la domanda di conferma.
- Non eseguire due conferme consecutive.
- Se il cliente non dice un sì chiaro, non chiamare il tool di scrittura.
- Considera come conferma esplicita anche formule naturali come:
  "sì", "certo", "va bene", "perfetto", "d'accordo", "confermo", "proceda".
- Se la conferma è ambigua, chiedi una sola volta in modo naturale e breve.
- Non dire mai al cliente quali parole esatte deve usare per confermare.
- Non usare formule rigide come "Mi serve un sì chiaro" o "basta dire sì".
- Se hai già chiesto la conferma una volta e ancora non è chiara, non insistere:
  passa a un umano.

Duplicate Prevention
- Non creare mai prenotazioni duplicate.
- Se risulta già una prenotazione attiva dello stesso chiamante nello stesso giorno e orario:
  - dillo chiaramente
  - offri di lasciarla così, modificarla o cancellarla
  - trasferisci solo se il cliente chiede il ristorante o il caso esce dal perimetro
  - formula breve possibile:
    "Risulta già una prenotazione da questo numero. Posso lasciarla così, modificarla o cancellarla."

Safety & Escalation
- Escala solo quando serve davvero. Non usare il trasferimento come scorciatoia.
- Escala subito se il cliente lo chiede.
- Escala subito se il gruppo supera {large_group_threshold} persone.
- Escala subito se emergono allergie o richieste fuori policy.
- Escala se l'audio resta poco chiaro dopo due tentativi mirati sulla stessa informazione obbligatoria.
- Escala se due tentativi di tool sulla stessa richiesta falliscono.
- Escala se la chiamata supera circa 90 secondi o 8 turni dell'assistente senza chiusura chiara.
- Non escalare se puoi ancora risolvere con una sola domanda mirata.
- Formula: "La metto in contatto con il ristorante."
- Dopo un'azione completata con successo, chiudi subito con cortesia.
- Dopo una risposta informativa completa, chiudi subito con cortesia.

Unclear Audio
- Se non capisci qualcosa, chiedi solo la parte mancante.
- Non indovinare mai.
- Se non hai sentito bene nome, orario, numero persone, data o conferma, chiedi di ripetere solo quel pezzo.
- Se la risposta sembra incompatibile con la domanda, correggi subito:
  "Mi scusi, non ho capito bene quel dettaglio. Può ripetere solo l'orario?"
- Non dire "perfetto" dopo una risposta poco chiara o senza senso.
- Se una conferma finale non è chiara, usa una sola riparazione morbida, ad esempio:
  "Non ho colto bene la conferma. Se per lei va bene, procedo subito."
- Massimo due tentativi per la stessa informazione, poi escala.
""".strip()


def build_realtime_tools(
    *,
    tool_names: tuple[str, ...] = FULL_TOOL_NAMES,
) -> list[dict[str, Any]]:
    tools = [
        {
            "type": "function",
            "name": "check_availability",
            "description": (
                "Verifica la disponibilità per una richiesta di prenotazione. "
                "Usalo SOLO quando il cliente ha esplicitamente detto data E numero di persone. "
                "NON chiamare con dati inventati o assunti."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": (
                            "Data in formato YYYY-MM-DD. Converti riferimenti relativi "
                            "(domani, dopodomani) in data assoluta. "
                            "DEVE provenire da ciò che il cliente ha detto."
                        ),
                    },
                    "party_size": {
                        "type": "integer",
                        "description": (
                            "Numero di persone. DEVE essere un numero esplicitamente "
                            "detto dal cliente. Non inventare."
                        ),
                    },
                    "time_preference": {
                        "type": "string",
                        "description": (
                            "Orario preferito in formato HH:MM:SS. Omettilo se il cliente "
                            "non ha indicato un orario preciso."
                        ),
                    },
                },
                "required": ["date", "party_size"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "find_booking",
            "description": (
                "Cerca prenotazioni esistenti del chiamante o tramite codice. "
                "Usalo per verifica, modifica, cancellazione e controllo duplicati."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {
                        "type": "string",
                        "description": "Codice prenotazione se il cliente lo fornisce.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "create_booking",
            "description": (
                "Crea una nuova prenotazione confermata. "
                "REQUISITI: 1) check_availability già chiamato con esito positivo, "
                "2) tutti i dati raccolti ESPLICITAMENTE dal cliente "
                "(data, ora, persone, nome), "
                "3) conferma esplicita del cliente (sì/confermo). "
                "NON usare dati inventati o assunti. "
                "Se il tool restituisce conferma mancante, NON richiamarlo "
                "finché il cliente non dice un sì chiaro nel turno successivo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": (
                            "Data in formato YYYY-MM-DD. Deve corrispondere a "
                            "check_availability."
                        ),
                    },
                    "time": {
                        "type": "string",
                        "description": (
                            "Orario in formato HH:MM:SS. Usa SOLO uno slot restituito da "
                            "check_availability."
                        ),
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Numero esatto di coperti DETTO dal cliente.",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Solo il nome DETTO dal cliente. Non inventare.",
                    },
                    "special_requests": {
                        "type": "string",
                        "description": (
                            "Solo richieste non critiche citate spontaneamente dal cliente. "
                            "Ometti allergie o richieste fuori policy."
                        ),
                    },
                },
                "required": ["date", "time", "party_size", "customer_name"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "modify_booking",
            "description": (
                "Modifica una prenotazione esistente. "
                "Usalo solo dopo conferma esplicita del cliente e solo per i campi "
                "che cambiano davvero. Se manca un sì chiaro, non ripetere subito il tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {
                        "type": "string",
                        "description": "Codice della prenotazione da modificare.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Nuova data in formato YYYY-MM-DD.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Nuovo orario in formato HH:MM:SS.",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Nuovo numero di coperti.",
                    },
                    "customer_name": {"type": "string", "description": "Nuovo nome se richiesto."},
                    "customer_phone": {
                        "type": "string",
                        "description": "Nuovo numero se richiesto.",
                    },
                    "special_requests": {
                        "type": "string",
                        "description": "Nuove richieste speciali.",
                    },
                },
                "required": ["confirmation_code"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "cancel_booking",
            "description": (
                "Cancella una prenotazione esistente. "
                "Usalo solo dopo conferma esplicita del cliente. "
                "Se manca un sì chiaro, non ripetere subito il tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {
                        "type": "string",
                        "description": "Codice della prenotazione da cancellare.",
                    },
                },
                "required": ["confirmation_code"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "escalate_to_human",
            "description": (
                "Trasferisce la chiamata a un umano quando il flusso richiede "
                "assistenza del ristorante."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Motivo sintetico dell'escalation.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    ]
    return [tool for tool in tools if tool["name"] in tool_names]


def build_session_update(
    restaurant: Restaurant,
    *,
    caller_phone: str,
    output_modalities: tuple[str, ...] = ("audio",),
    prompt_override: str | None = None,
    overrides: RealtimeSessionOverrides | None = None,
    include_diagnostics: bool = False,
    tool_names: tuple[str, ...] = READ_ONLY_TOOL_NAMES,
) -> dict[str, Any]:
    tuning = merged_session_overrides(restaurant, overrides)

    # -- Turn detection (flat session field per API spec) -------------------
    if tuning.turn_detection_type == "semantic_vad":
        turn_detection: dict[str, Any] = {
            "type": "semantic_vad",
            "eagerness": tuning.semantic_vad_eagerness,
            "create_response": tuning.create_response,
            "interrupt_response": tuning.interrupt_response,
        }
    else:
        turn_detection = {
            "type": "server_vad",
            "threshold": tuning.vad_threshold,
            "prefix_padding_ms": tuning.vad_prefix_padding_ms,
            "silence_duration_ms": tuning.vad_silence_duration_ms,
            "interrupt_response": tuning.interrupt_response,
            "create_response": tuning.create_response,
        }

    # -- Session payload (GA shape for current Realtime WebSocket interface) --
    session: dict[str, Any] = {
        "type": "realtime",
        "model": tuning.model or settings.openai_realtime_model,
        "instructions": build_realtime_instructions(
            restaurant,
            caller_phone=caller_phone,
            prompt_override=prompt_override,
        ),
        "audio": {
            "input": {
                "format": {"type": "audio/pcmu"},
                "transcription": {
                    "model": tuning.transcription_model,
                    "prompt": _transcription_prompt(restaurant),
                },
                "turn_detection": turn_detection,
            }
        },
        "tools": build_realtime_tools(tool_names=tool_names),
        "tool_choice": tuning.tool_choice,
        "parallel_tool_calls": False,
        "tracing": "auto" if tuning.tracing_enabled else None,
    }
    if tuning.turn_detection_type == "server_vad":
        session["audio"]["input"]["turn_detection"]["idle_timeout_ms"] = tuning.vad_idle_timeout_ms

    if "audio" in output_modalities:
        session["audio"]["output"] = {
            "format": {"type": "audio/pcmu"},
            "voice": tuning.voice or settings.openai_realtime_voice,
        }

    if tuning.noise_reduction_type != "off":
        session["audio"]["input"]["noise_reduction"] = {"type": tuning.noise_reduction_type}
    if tuning.input_language:
        session["audio"]["input"]["transcription"]["language"] = tuning.input_language

    if tuning.truncation_mode == "retention_ratio":
        session["truncation"] = {
            "type": "retention_ratio",
            "retention_ratio": tuning.truncation_retention_ratio,
        }

    if include_diagnostics:
        session["include"] = ["item.input_audio_transcription.logprobs"]

    return {"type": "session.update", "session": session}


def _build_tool_scope_update(
    *,
    tool_names: tuple[str, ...],
    overrides: RealtimeSessionOverrides,
) -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "tools": build_realtime_tools(tool_names=tool_names),
            "tool_choice": overrides.tool_choice,
        },
    }


def _buffer_twilio_media_payload(
    state: RealtimeCallState,
    *,
    payload: str,
    buffered_audio: bytearray,
    buffered_packets: int,
) -> int:
    if state.initial_greeting_in_progress or (
        state.initial_greeting_grace_until and datetime.now(UTC) < state.initial_greeting_grace_until
    ):
        state.dropped_input_audio_packets += 1
        return buffered_packets
    try:
        decoded = base64.b64decode(payload)
    except Exception:
        return buffered_packets
    if not decoded:
        return buffered_packets
    buffered_audio.extend(decoded)
    return buffered_packets + 1


def studio_readiness(restaurant: Restaurant) -> list[dict[str, str]]:
    public_base_url = (settings.public_base_url or "").strip()
    readiness = [
        {
            "label": "OpenAI API key",
            "status": "good" if settings.openai_api_key else "warn",
            "detail": (
                "Presente: il bridge realtime puo aprire una sessione live."
                if settings.openai_api_key
                else "Manca OPENAI_API_KEY: simulazioni realtime e chiamate vere non partiranno."
            ),
        },
        {
            "label": "PUBLIC_BASE_URL",
            "status": "good" if public_base_url else "warn",
            "detail": (
                f"Configurato su {public_base_url}."
                if public_base_url
                else "Manca PUBLIC_BASE_URL: Twilio non sapra dove aprire stream e callback."
            ),
        },
        {
            "label": "Twilio number",
            "status": "good" if restaurant.twilio_phone else "warn",
            "detail": (
                f"Numero attivo: {restaurant.twilio_phone}."
                if restaurant.twilio_phone
                else "Il ristorante non ha ancora un numero Twilio assegnato."
            ),
        },
        {
            "label": "Voice provider",
            "status": "good" if restaurant.voice_provider == "openai_realtime" else "warn",
            "detail": (
                "Il ristorante usa OpenAI Realtime come runtime live."
                if restaurant.voice_provider == "openai_realtime"
                else f"Il ristorante risulta ancora su {restaurant.voice_provider}."
            ),
        },
        {
            "label": "Tool secret",
            "status": "good" if settings.tool_secret else "warn",
            "detail": (
                "Presente: il percorso tool HTTP resta verificabile e i test backend possono usare lo stesso secret."
                if settings.tool_secret
                else "Manca TOOL_SECRET: i controlli e le integrazioni tool esterne non sono protetti correttamente."
            ),
        },
        {
            "label": "Escalation path",
            "status": (
                "good"
                if restaurant.escalation_phone and settings.twilio_account_sid and settings.twilio_auth_token
                else "warn"
            ),
            "detail": (
                f"Trasferimento live pronto verso {restaurant.escalation_phone}."
                if restaurant.escalation_phone and settings.twilio_account_sid and settings.twilio_auth_token
                else (
                    "Per trasferire una chiamata servono escalation_phone del ristorante "
                    "e credenziali Twilio lato backend."
                )
            ),
        },
    ]
    return readiness


def studio_checklist(session_update: dict[str, Any]) -> list[dict[str, str]]:
    session = session_update["session"]
    audio_input = ((session.get("audio") or {}).get("input") or {})
    turn_detection = audio_input.get("turn_detection") or {}
    truncation = session.get("truncation")
    tool_count = len(session.get("tools") or [])
    checks = [
        {
            "label": "GA session shape",
            "status": "good" if session.get("type") == "realtime" else "warn",
            "detail": "La sessione deve dichiarare type=realtime per restare allineata alla GA interface.",
        },
        {
            "label": "Prompt strutturato",
            "status": "good" if "Role & Objective" in session["instructions"] else "warn",
            "detail": "Sezioni dedicate migliorano instruction following e debugging.",
        },
        {
            "label": "Lingua vincolata",
            "status": "good" if "Language" in session["instructions"] else "warn",
            "detail": "Riduce i cambi di lingua indesiderati nelle chiamate rumorose.",
        },
        {
            "label": "Preamboli tool",
            "status": "good" if "Controllo subito." in session["instructions"] else "warn",
            "detail": "Piccoli preamboli evitano silenzi strani durante i tool call.",
        },
        {
            "label": "Noise reduction",
            "status": "good" if audio_input.get("noise_reduction") else "warn",
            "detail": "Aiuta con telefono, bar e sala rumorosa.",
        },
        {
            "label": "Turn detection",
            "status": "good" if turn_detection else "warn",
            "detail": "VAD o semantic turn detection necessari per conversazione naturale.",
        },
        {
            "label": "Idle timeout",
            "status": (
                "good"
                if isinstance(turn_detection, dict)
                and (turn_detection.get("type") != "server_vad" or turn_detection.get("idle_timeout_ms"))
                else "warn"
            ),
            "detail": "L'idle timeout aiuta il modello a recuperare da VAD mancati o linee poco chiare.",
        },
        {
            "label": "Truncation controllata",
            "status": "good"
            if isinstance(truncation, dict) and truncation.get("retention_ratio", 1.0) < 1.0
            else "warn",
            "detail": "Riduce costi e cache busting nelle chiamate più lunghe.",
        },
        {
            "label": "Tool scope limitato",
            "status": "good" if tool_count <= 6 else "warn",
            "detail": "OpenAI consiglia agenti vocali focalizzati, con pochi tool e un escape hatch chiaro.",
        },
        {
            "label": "Tracing attivo",
            "status": "good" if session.get("tracing") else "warn",
            "detail": "Permette ispezione delle sessioni in produzione.",
        },
        {
            "label": "Guard rail di scrittura",
            "status": "good",
            "detail": "Create, modify e cancel sono bloccati lato server senza conferma valida.",
        },
    ]
    return checks


def studio_prompt_diagnostics(prompt: str) -> list[dict[str, str]]:
    normalized = prompt.strip()
    lower_prompt = normalized.lower()
    diagnostics = [
        {
            "label": "Structured sections",
            "status": "good" if all(section in normalized for section in PROMPT_SECTIONS) else "warn",
            "detail": (
                "Il prompt dovrebbe mantenere sezioni etichettate per ruolo, strumenti, "
                "flusso, sicurezza e audio poco chiaro."
            ),
        },
        {
            "label": "Language pinning",
            "status": (
                "good"
                if "language" in lower_prompt
                and ("segui la lingua del cliente" in lower_prompt or "italiano" in lower_prompt)
                else "warn"
            ),
            "detail": (
                "Serve una regola esplicita sulla lingua: "
                "o segui il cliente, o imponi un solo idioma senza conflitti."
            ),
        },
        {
            "label": "Bullets over paragraphs",
            "status": "good" if normalized.count("\n- ") >= 12 else "warn",
            "detail": "La guida Realtime raccomanda bullet chiari e brevi invece di paragrafi lunghi.",
        },
        {
            "label": "Tool preambles",
            "status": "good" if "controllo subito" in lower_prompt or "verifico adesso" in lower_prompt else "warn",
            "detail": (
                "Un preambolo corto prima del tool aiuta a evitare silenzi strani "
                "e riduce la percezione di instabilita."
            ),
        },
        {
            "label": "Write confirmation guard",
            "status": (
                "good"
                if "conferma esplicita" in lower_prompt and "stesso turno" in lower_prompt
                else "warn"
            ),
            "detail": (
                "Il prompt dovrebbe ribadire che create, modify e cancel avvengono "
                "solo dopo una conferma separata."
            ),
        },
        {
            "label": "Escalation wording",
            "status": "good" if "la metto in contatto con il ristorante" in lower_prompt else "warn",
            "detail": "Una frase di handoff stabile rende il trasferimento piu coerente e piu testabile.",
        },
        {
            "label": "Variety rule",
            "status": "good" if "varia" in lower_prompt or "non ripetere" in lower_prompt else "warn",
            "detail": "Serve una regola esplicita contro la ripetizione per evitare che l'agente sembri meccanico.",
        },
        {
            "label": "Escape hatch",
            "status": "good" if "la metto in contatto con il ristorante" in lower_prompt else "warn",
            "detail": "Un agente vocale robusto deve avere un handoff chiaro quando il caso esce dal perimetro.",
        },
        {
            "label": "Examples and sample phrases",
            "status": (
                "good"
                if "\"mi chiamo edoardo\"" in lower_prompt or "\"controllo subito" in lower_prompt
                else "warn"
            ),
            "detail": "Il modello segue bene esempi brevi di frasi target per identita, preamboli ed escalation.",
        },
    ]
    return diagnostics


def studio_recommendations(
    *,
    restaurant: Restaurant,
    prompt: str,
    effective_overrides: RealtimeSessionOverrides,
    session_update: dict[str, Any],
) -> list[dict[str, str]]:
    session = session_update["session"]
    audio_input = ((session.get("audio") or {}).get("input") or {})
    turn_detection = audio_input.get("turn_detection") or {}
    recommendations = [
        {
            "label": "Focused task scope",
            "status": "good" if len(build_realtime_tools()) <= 6 else "warn",
            "detail": "Per voice agents OpenAI consiglia pochi tool e un solo compito ben definito.",
        },
        {
            "label": "Critical facts in prompt",
            "status": "good" if "Context" in prompt and "Orari" in prompt and "Indirizzo" in prompt else "warn",
            "detail": (
                "Le informazioni operative importanti dovrebbero stare nel "
                "prompt, non dipendere da tool iniziali."
            ),
        },
        {
            "label": "Recommended voice",
            "status": (
                "good"
                if (effective_overrides.voice or settings.openai_realtime_voice)
                in RECOMMENDED_REALTIME_VOICES
                else "warn"
            ),
            "detail": "Marin e Cedar sono le voci più solide per questo flusso telefonico finora.",
        },
        {
            "label": "Tool choice mode",
            "status": "good" if session.get("tool_choice") == "auto" else "warn",
            "detail": "AUTO è la scelta più stabile qui: lascia usare i tool quando servono ma evita rigidità inutile.",
        },
        {
            "label": "Flexible input language",
            "status": (
                "good"
                if audio_input.get("transcription", {}).get("language") in {None, "", "it", "en"}
                else "warn"
            ),
            "detail": (
                "Lasciare la trascrizione senza pinning rigido aiuta quando il chiamante cambia lingua; "
                "usa un codice ISO solo se vuoi forzare una lingua."
            ),
        },
        {
            "label": "Turn patience for phone calls",
            "status": (
                "good"
                if turn_detection.get("type") == "server_vad"
                and int(turn_detection.get("silence_duration_ms") or 0) >= 600
                else "warn"
            ),
            "detail": "Per telefonate reali conviene evitare un end-of-turn troppo aggressivo.",
        },
        {
            "label": "Context cost control",
            "status": "good" if isinstance(session.get("truncation"), dict) else "warn",
            "detail": (
                "Le chiamate lunghe costano di più a ogni turno: "
                "retention_ratio aiuta a contenere costo e drift."
            ),
        },
        {
            "label": "Human escape hatch",
            "status": (
                "good"
                if restaurant.escalation_phone
                or "la metto in contatto con il ristorante" in prompt.lower()
                else "warn"
            ),
            "detail": "Il sistema deve poter mollare rapidamente i casi fuori policy o troppo ambigui.",
        },
    ]
    return recommendations


def studio_presets() -> list[dict[str, Any]]:
    return STUDIO_PRESETS


def studio_scenarios() -> list[dict[str, str]]:
    return STUDIO_SCENARIOS


def studio_config_diff(
    restaurant: Restaurant,
    effective_overrides: RealtimeSessionOverrides,
) -> list[dict[str, str]]:
    baseline = default_session_overrides()
    saved = restaurant.openai_realtime_settings or {}
    diff: list[dict[str, str]] = []
    for field_name in RealtimeSessionOverrides.__dataclass_fields__.keys():
        baseline_value = getattr(baseline, field_name)
        effective_value = getattr(effective_overrides, field_name)
        if baseline_value == effective_value:
            continue
        diff.append(
            {
                "field": field_name,
                "label": OVERRIDE_FIELD_LABELS.get(field_name, field_name.replace("_", " ").title()),
                "baseline": _format_override_value(baseline_value),
                "effective": _format_override_value(effective_value),
                "source": "saved" if field_name in saved else "runtime",
            }
        )
    if not diff:
        diff.append(
            {
                "field": "defaults",
                "label": "Runtime defaults",
                "baseline": "system defaults",
                "effective": "system defaults",
                "source": "default",
            }
        )
    return diff


def studio_practical_config_diff(
    restaurant: Restaurant,
    effective_overrides: RealtimeSessionOverrides,
) -> list[dict[str, str]]:
    return [
        item
        for item in studio_config_diff(restaurant, effective_overrides)
        if item["field"] == "defaults" or item["field"] in PRACTICAL_STUDIO_FIELDS
    ]


def _text_has_confirmation_cue(text: str) -> bool:
    lowered = text.lower()
    return any(cue in lowered for cue in CONFIRMATION_CUES)


def _text_is_affirmative(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in AFFIRMATIVE_WORDS)


def _ingest_assistant_transcript(state: RealtimeCallState, transcript: str) -> None:
    """Record a completed assistant turn and update the confirmation state.

    The confirmation flag is only set — never cleared here — so a short filler
    utterance emitted alongside a tool call (e.g. "Un momento.") cannot erase the
    confirmation cue from the previous assistant turn. The flags are reset only
    after a write tool actually runs.
    """
    state.last_assistant_transcript = transcript
    if _text_has_confirmation_cue(transcript):
        state.awaiting_confirmation = True


def _ingest_user_transcript(state: RealtimeCallState, transcript: str) -> None:
    """Record a completed user turn and mark confirmation as granted if applicable."""
    state.last_user_transcript = transcript
    if state.awaiting_confirmation and _text_is_affirmative(transcript):
        state.confirmation_granted = True


def _ingest_input_audio_transcription_delta(
    state: RealtimeCallState,
    *,
    item_id: str | None,
    delta: str,
) -> str:
    """Track incremental user transcription so short confirmations land early."""
    cleaned_delta = delta.strip()
    if not cleaned_delta:
        return ""
    key = item_id or "unknown"
    combined = f"{state.pending_user_audio_transcripts.get(key, '')}{delta}".strip()
    state.pending_user_audio_transcripts[key] = combined
    if state.awaiting_confirmation and _text_is_affirmative(combined):
        state.confirmation_granted = True
    return combined


def _reset_confirmation_state(state: RealtimeCallState) -> None:
    state.awaiting_confirmation = False
    state.confirmation_granted = False


def _write_confirmation_granted(state: RealtimeCallState) -> bool:
    return state.confirmation_granted


def _sync_call_update(
    db_factory: sessionmaker,
    *,
    call_sid: str,
    fields: dict[str, Any],
) -> None:
    db: Session = db_factory()
    try:
        call = db.scalar(select(CallLog).where(CallLog.twilio_call_sid == call_sid))
        if not call:
            return
        for field, value in fields.items():
            if field == "extra_data" and isinstance(value, dict):
                current = call.extra_data if isinstance(call.extra_data, dict) else {}
                setattr(call, field, {**current, **value})
                continue
            setattr(call, field, value)
        db.add(call)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _update_call(
    db_factory: sessionmaker,
    *,
    call_sid: str,
    **fields: Any,
) -> None:
    await asyncio.to_thread(_sync_call_update, db_factory, call_sid=call_sid, fields=fields)


def _modify_changes_from_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    changes = {
        key: arguments[key]
        for key in ["date", "time", "party_size", "customer_name", "customer_phone", "special_requests"]
        if arguments.get(key) is not None
    }
    return ModifyBookingChanges.model_validate(changes).model_dump(exclude_unset=True)


def _sync_dispatch_tool(
    db_factory: sessionmaker,
    *,
    restaurant: Restaurant,
    state: RealtimeCallState,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    db: Session = db_factory()
    try:
        try:
            if tool_name == "check_availability":
                return check_availability(
                    db,
                    restaurant=restaurant,
                    booking_date=date.fromisoformat(arguments["date"]),
                    requested_time=(
                        time.fromisoformat(arguments["time_preference"])
                        if arguments.get("time_preference")
                        else None
                    ),
                    party_size=int(arguments["party_size"]),
                )

            if tool_name == "find_booking":
                bookings = find_bookings_for_caller(
                    db,
                    restaurant_id=restaurant.id,
                    caller_phone=state.caller_phone or None,
                    confirmation_code=arguments.get("confirmation_code"),
                )
                return {
                    "found": bool(bookings),
                    "bookings": [booking.model_dump(mode="json") for booking in bookings],
                }

            if tool_name == "create_booking":
                if not _write_confirmation_granted(state):
                    return _missing_confirmation_result(state)
                _reset_confirmation_state(state)
                existing_bookings = find_bookings_for_caller(
                    db,
                    restaurant_id=restaurant.id,
                    caller_phone=state.caller_phone or None,
                    confirmation_code=None,
                )
                duplicate_booking = next(
                    (
                        booking
                        for booking in existing_bookings
                        if str(booking.date) == str(arguments["date"])
                        and str(booking.time) == str(arguments["time"])
                        and booking.status in ACTIVE_STATUSES
                    ),
                    None,
                )
                if duplicate_booking:
                    return {
                        "success": False,
                        "reason": (
                            "Risulta già una prenotazione attiva da questo numero nello stesso giorno e orario."
                        ),
                        "duplicate_booking": duplicate_booking.model_dump(mode="json"),
                        "retry_write": False,
                        "should_escalate": False,
                        "can_self_service": True,
                        "assistant_instruction": (
                            "Non creare una seconda prenotazione. Di' che esiste già una prenotazione "
                            "da questo numero per lo stesso giorno e orario e offri di lasciarla così, "
                            "modificarla o cancellarla. Passa al ristorante solo se il cliente lo chiede."
                        ),
                    }
                booking, error = create_booking(
                    db,
                    payload=BookingCreate(
                        restaurant_id=restaurant.id,
                        date=date.fromisoformat(arguments["date"]),
                        time=time.fromisoformat(arguments["time"]),
                        party_size=int(arguments["party_size"]),
                        customer_name=str(
                            arguments.get("customer_name") or arguments.get("name") or ""
                        ).strip(),
                        customer_phone=state.caller_phone,
                        special_requests=arguments.get("special_requests"),
                        source=BookingSource.ai_phone,
                        status=BookingStatus.confirmed,
                    ),
                    changed_by="openai_realtime",
                )
                if error:
                    db.rollback()
                    return {"success": False, **error}
                db.commit()
                state.outcome = "booking_created"
                state.end_call_after_response = True
                return {"success": True, "confirmation_code": booking.confirmation_code}

            if tool_name == "modify_booking":
                if not _write_confirmation_granted(state):
                    return _missing_confirmation_result(state)
                _reset_confirmation_state(state)
                changes = _modify_changes_from_arguments(arguments)
                if not changes:
                    return {"success": False, "reason": "Nessuna modifica valida fornita."}
                booking = db.scalar(
                    select(Booking).where(
                        Booking.restaurant_id == restaurant.id,
                        Booking.confirmation_code == arguments["confirmation_code"],
                        Booking.status.in_(ACTIVE_STATUSES),
                    )
                )
                if not booking:
                    return {"success": False, "reason": "Prenotazione non trovata."}
                updated, error = update_booking(
                    db,
                    booking=booking,
                    changes=BookingUpdate(**changes),
                    changed_by="openai_realtime",
                )
                if error:
                    db.rollback()
                    return {"success": False, **error}
                db.commit()
                state.outcome = "booking_modified"
                state.end_call_after_response = True
                return {"success": True, "updated_booking": updated.id}

            if tool_name == "cancel_booking":
                if not _write_confirmation_granted(state):
                    return _missing_confirmation_result(state)
                _reset_confirmation_state(state)
                booking = db.scalar(
                    select(Booking).where(
                        Booking.restaurant_id == restaurant.id,
                        Booking.confirmation_code == arguments["confirmation_code"],
                        Booking.status.in_(ACTIVE_STATUSES),
                    )
                )
                if not booking:
                    return {"success": False, "reason": "Prenotazione non trovata."}
                booking.status = "cancelled"
                db.add(booking)
                db.commit()
                state.outcome = "booking_cancelled"
                state.end_call_after_response = True
                return {"success": True}

            if tool_name == "escalate_to_human":
                state.outcome = "escalated"
                if state.twilio_call_sid.startswith("studio-"):
                    return {
                        "success": True,
                        "transferred": True,
                        "simulated": True,
                        "reason": arguments.get("reason"),
                    }
                transferred = _sync_transfer_call_to_restaurant(
                    restaurant=restaurant,
                    call_sid=state.twilio_call_sid,
                )
                return {
                    "success": transferred,
                    "transferred": transferred,
                    "reason": arguments.get("reason"),
                }

            return {"success": False, "reason": f"Tool sconosciuto: {tool_name}"}
        except Exception as exc:
            db.rollback()
            state.technical_tool_failures += 1
            json_log(
                "app.realtime",
                {
                    "event": "openai_tool_dispatch_failed",
                    "restaurant_id": restaurant.id,
                    "call_sid": state.twilio_call_sid,
                    "tool_name": tool_name,
                    "error": str(exc),
                    "technical_tool_failures": state.technical_tool_failures,
                },
            )
            return {
                "success": False,
                "reason": "Errore tecnico temporaneo del sistema.",
                "technical_error": True,
                "technical_tool_failures": state.technical_tool_failures,
                "should_escalate": state.technical_tool_failures >= 2,
            }
    finally:
        db.close()


async def dispatch_tool(
    db_factory: sessionmaker,
    *,
    restaurant: Restaurant,
    state: RealtimeCallState,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _sync_dispatch_tool,
        db_factory,
        restaurant=restaurant,
        state=state,
        tool_name=tool_name,
        arguments=arguments,
    )


def _sync_end_twilio_call(*, restaurant: Restaurant, call_sid: str) -> bool:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return False
    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls/{call_sid}.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={"Twiml": "<Response><Hangup/></Response>"},
        timeout=10.0,
    )
    return response.is_success


async def _end_twilio_call_after_delay(*, restaurant: Restaurant, call_sid: str, delay_ms: int) -> None:
    await asyncio.sleep(max(delay_ms, 0) / 1000)
    with suppress(Exception):
        await asyncio.to_thread(_sync_end_twilio_call, restaurant=restaurant, call_sid=call_sid)


def _sync_transfer_call_to_restaurant(*, restaurant: Restaurant, call_sid: str) -> bool:
    if not settings.twilio_account_sid or not settings.twilio_auth_token or not restaurant.escalation_phone:
        return False
    twiml = f"<Response><Dial>{restaurant.escalation_phone}</Dial></Response>"
    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls/{call_sid}.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={"Twiml": twiml},
        timeout=10.0,
    )
    return response.is_success


async def _send_response_create(
    realtime_ws,
    *,
    output_modalities: tuple[str, ...] = ("audio",),
) -> None:
    response: dict[str, Any] = {"output_modalities": ["audio"] if "audio" in output_modalities else ["text"]}
    if "audio" in output_modalities:
        response["audio"] = {"output": {"format": {"type": "audio/pcmu"}}}
    await realtime_ws.send(json.dumps({"type": "response.create", "response": response}))


async def _send_runtime_context_message(realtime_ws: Any, restaurant: Restaurant, *, caller_phone: str) -> None:
    await realtime_ws.send(
        json.dumps(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _runtime_context_message(restaurant, caller_phone=caller_phone),
                        }
                    ],
                },
            }
        )
    )


def _current_tool_scope(state: RealtimeCallState) -> tuple[str, ...]:
    if state.confirmation_granted:
        return FULL_TOOL_NAMES
    if state.end_call_after_response:
        return ("escalate_to_human",)
    return READ_ONLY_TOOL_NAMES


async def _sync_tool_scope(
    realtime_ws: Any,
    restaurant: Restaurant,
    state: RealtimeCallState,
    *,
    caller_phone: str,
    output_modalities: tuple[str, ...] = ("audio",),
    prompt_override: str | None = None,
    overrides: RealtimeSessionOverrides | None = None,
) -> None:
    tuning = merged_session_overrides(restaurant, overrides)
    await realtime_ws.send(
        json.dumps(
            _build_tool_scope_update(
                tool_names=_current_tool_scope(state),
                overrides=tuning,
            )
        )
    )


def _audio_duration_ms_from_payload(delta: str) -> int:
    try:
        return int((len(base64.b64decode(delta)) / 8000) * 1000)
    except Exception:
        return 0


def _finish_initial_greeting(state: RealtimeCallState) -> None:
    if not state.initial_greeting_in_progress:
        return
    state.initial_greeting_in_progress = False
    # Leave a short post-greeting gate to avoid line echo being transcribed as
    # a phantom first user turn on PSTN calls.
    state.initial_greeting_grace_until = datetime.now(UTC) + timedelta(milliseconds=600)


async def _truncate_unplayed_audio(state: RealtimeCallState, realtime_ws: Any, websocket: WebSocket) -> None:
    if not state.last_audio_item_id or state.last_audio_bytes_sent <= 0 or not state.stream_sid:
        return
    await websocket.send_json({"event": "clear", "streamSid": state.stream_sid})
    audio_end_ms = int((state.last_audio_bytes_sent / 8000) * 1000)
    if audio_end_ms <= 0:
        return
    await realtime_ws.send(
        json.dumps(
            {
                "type": "conversation.item.truncate",
                "item_id": state.last_audio_item_id,
                "content_index": state.last_audio_content_index,
                "audio_end_ms": audio_end_ms,
            }
        )
    )
    state.last_audio_item_id = None
    state.last_audio_content_index = 0
    state.last_audio_bytes_sent = 0
    state.assistant_is_speaking = False


async def _summarize_conversation_turns(turns: list[dict[str, str]]) -> str:
    if not turns or not settings.openai_api_key:
        return ""
    transcript = "\n".join(f"{turn['role']}: {turn['text']}" for turn in turns if turn.get("text"))
    if not transcript.strip():
        return ""
    prompt = _build_conversation_summary_prompt(turns)
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": SUMMARY_MODEL,
                    "input": prompt,
                    "max_output_tokens": 220,
                },
            )
            response.raise_for_status()
    except Exception:
        return ""
    payload = response.json()
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(str(text).strip())
    return "\n".join(part for part in parts if part).strip()


async def _maybe_refresh_summary(
    *,
    realtime_ws: Any,
    db_factory: sessionmaker,
    restaurant: Restaurant,
    state: RealtimeCallState,
    call_sid: str,
) -> None:
    if len(state.conversation_turns) < SUMMARY_TRIGGER_TURNS:
        return
    candidate_turns = state.conversation_turns[:-SUMMARY_KEEP_LAST_TURNS]
    if len(candidate_turns) < SUMMARY_KEEP_LAST_TURNS:
        return
    summary = await _summarize_conversation_turns(candidate_turns)
    if not summary or summary == state.latest_summary:
        return
    state.latest_summary = summary
    await realtime_ws.send(
        json.dumps(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Riassunto conversazione fin qui:\n{summary}"}],
                },
            }
        )
    )
    await _update_call(
        db_factory,
        call_sid=call_sid,
        extra_data={"conversation_summary": summary},
    )


async def _run_silent_response_watchdog(
    *,
    realtime_ws: Any,
    restaurant: Restaurant,
    state: RealtimeCallState,
    caller_phone: str,
    generation: int,
) -> None:
    await asyncio.sleep(SILENT_RESPONSE_WATCHDOG_SECONDS)
    if generation != state.response_watchdog_generation:
        return
    if not state.response_in_progress or state.response_audio_started:
        return
    if state.silent_response_retries >= MAX_SILENT_RESPONSE_RETRIES:
        return
    state.silent_response_retries += 1
    state.response_in_progress = False
    with suppress(Exception):
        await realtime_ws.send(json.dumps({"type": "response.cancel"}))
        await _sync_tool_scope(realtime_ws, restaurant, state, caller_phone=caller_phone)
        await _send_response_create(realtime_ws, output_modalities=("audio",))


async def bridge_twilio_media_stream(
    *,
    websocket: WebSocket,
    db_factory: sessionmaker,
) -> None:
    initial_event = await websocket.receive_json()
    if initial_event.get("event") == "connected":
        initial_event = await websocket.receive_json()

    if initial_event.get("event") != "start":
        raise RuntimeError("Twilio stream did not send a start event.")

    start = initial_event.get("start", {})
    custom_parameters = start.get("customParameters") or {}
    token = str(custom_parameters.get("token") or "").strip()
    if not token:
        raise RuntimeError("Twilio stream token missing.")

    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise RuntimeError("Twilio stream token invalid.") from exc

    db: Session = db_factory()
    try:
        restaurant = db.get(Restaurant, claims.get("restaurant_id"))
    finally:
        db.close()
    if not restaurant:
        raise RuntimeError("Restaurant not found for Twilio media stream.")

    call_sid = str(claims.get("call_sid") or "")
    from_number = str(claims.get("from_number") or "")
    to_number = str(claims.get("to_number") or "")
    state = RealtimeCallState(
        caller_phone=from_number,
        twilio_call_sid=call_sid,
        stream_sid=start.get("streamSid") or initial_event.get("streamSid"),
    )
    tuning = restaurant_session_overrides(restaurant)
    headers = realtime_headers()
    try:
        async with connect(realtime_ws_url(tuning.model), additional_headers=headers) as realtime_ws:
            await realtime_ws.send(
                json.dumps(
                    build_session_update(
                        restaurant,
                        caller_phone=from_number,
                        tool_names=_current_tool_scope(state),
                    )
                )
            )
            await _send_runtime_context_message(realtime_ws, restaurant, caller_phone=from_number)
            await _send_response_create(realtime_ws, output_modalities=("audio",))
            await _update_call(
                db_factory,
                call_sid=call_sid,
                twilio_call_sid=call_sid,
                voice_provider=restaurant.voice_provider,
            )

            async def twilio_to_openai() -> None:
                buffered_audio = bytearray()
                buffered_packets = 0

                async def flush_buffer() -> None:
                    nonlocal buffered_packets
                    if not buffered_audio:
                        buffered_audio.clear()
                        buffered_packets = 0
                        return
                    await realtime_ws.send(
                        json.dumps(
                            {
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(bytes(buffered_audio)).decode("ascii"),
                            }
                        )
                    )
                    buffered_audio.clear()
                    buffered_packets = 0

                while True:
                    event = await websocket.receive_json()
                    event_type = event.get("event")
                    if event_type == "media":
                        media = event.get("media", {})
                        payload = media.get("payload")
                        if payload:
                            buffered_packets = _buffer_twilio_media_payload(
                                state,
                                payload=payload,
                                buffered_audio=buffered_audio,
                                buffered_packets=buffered_packets,
                            )
                            if buffered_packets >= INPUT_AUDIO_BUFFER_PACKET_THRESHOLD:
                                await flush_buffer()
                    elif event_type == "dtmf":
                        digits = str((event.get("dtmf") or {}).get("digit") or "").strip()
                        if digits == "1":
                            await flush_buffer()
                            transferred = await asyncio.to_thread(
                                _sync_transfer_call_to_restaurant,
                                restaurant=restaurant,
                                call_sid=state.twilio_call_sid,
                            )
                            if not transferred:
                                raise RuntimeError("DTMF transfer to restaurant failed.")
                            state.outcome = "escalated"
                            state.end_call_after_response = transferred
                            break
                    elif event_type == "stop":
                        await flush_buffer()
                        break

            async def openai_to_twilio() -> None:
                async for raw_event in realtime_ws:
                    event = json.loads(raw_event)
                    event_type = event.get("type")

                    if event_type == "session.created":
                        session = event.get("session", {})
                        state.openai_session_id = session.get("id")
                        if state.openai_session_id:
                            await _update_call(
                                db_factory,
                                call_sid=call_sid,
                                provider_call_id=state.openai_session_id,
                            )
                        continue

                    if event_type == "input_audio_buffer.speech_started":
                        if state.response_in_progress:
                            await realtime_ws.send(json.dumps({"type": "response.cancel"}))
                        await _truncate_unplayed_audio(state, realtime_ws, websocket)
                        continue

                    if event_type == "conversation.item.input_audio_transcription.delta":
                        _ingest_input_audio_transcription_delta(
                            state,
                            item_id=str(event.get("item_id") or "unknown"),
                            delta=str(event.get("delta") or ""),
                        )
                        continue

                    if event_type == "conversation.item.input_audio_transcription.completed":
                        item_id = str(event.get("item_id") or "unknown")
                        partial_transcript = state.pending_user_audio_transcripts.pop(item_id, "")
                        transcript = str(event.get("transcript") or partial_transcript).strip()
                        if transcript:
                            _ingest_user_transcript(state, transcript)
                            _record_conversation_turn(state, role="user", text=transcript, item_id=item_id)
                            _append_transcript_line(state, "Cliente", transcript)
                            if state.confirmation_granted:
                                await _sync_tool_scope(
                                    realtime_ws,
                                    restaurant,
                                    state,
                                    caller_phone=from_number,
                                    output_modalities=("audio",),
                                )
                            if event.get("usage"):
                                state.transcription_events.append(
                                    {
                                        "transcript": transcript,
                                        "usage": event.get("usage"),
                                    }
                                )
                            await _update_call(
                                db_factory,
                                call_sid=call_sid,
                                transcript_preview="\n".join(state.transcript_lines[-20:]),
                            )
                        continue

                    if event_type == "response.created":
                        state.response_in_progress = True
                        state.response_audio_started = False
                        state.assistant_is_speaking = False
                        state.response_watchdog_generation += 1
                        asyncio.create_task(
                            _run_silent_response_watchdog(
                                realtime_ws=realtime_ws,
                                restaurant=restaurant,
                                state=state,
                                caller_phone=from_number,
                                generation=state.response_watchdog_generation,
                            )
                        )
                        continue

                    if event_type in {"response.output_item.added", "response.output_item.created"}:
                        item = event.get("item", {})
                        if item.get("type") == "message" and item.get("role") == "assistant":
                            state.last_audio_item_id = item.get("id")
                            state.last_audio_content_index = 0
                            state.last_audio_bytes_sent = 0
                        continue

                    if event_type in {"response.output_audio.delta", "response.audio.delta"} and state.stream_sid:
                        delta = event.get("delta")
                        if delta:
                            state.response_audio_started = True
                            state.assistant_is_speaking = True
                            state.silent_response_retries = 0
                            state.last_audio_bytes_sent += len(base64.b64decode(delta))
                            if event.get("item_id"):
                                state.last_audio_item_id = event["item_id"]
                            if event.get("content_index") is not None:
                                state.last_audio_content_index = int(event["content_index"])
                            await websocket.send_json(
                                {
                                    "event": "media",
                                    "streamSid": state.stream_sid,
                                    "media": {"payload": delta},
                                }
                            )
                        continue

                    if event_type == "response.output_audio.done":
                        _finish_initial_greeting(state)
                        state.assistant_is_speaking = False
                        continue

                    if event_type == "response.output_audio_transcript.delta":
                        delta = str(event.get("delta") or "")
                        if delta:
                            state.pending_assistant_audio_transcript += delta
                        continue

                    if event_type == "response.output_audio_transcript.done":
                        transcript = state.pending_assistant_audio_transcript.strip()
                        state.pending_assistant_audio_transcript = ""
                        if transcript:
                            _ingest_assistant_transcript(state, transcript)
                            _record_conversation_turn(state, role="assistant", text=transcript)
                            _append_transcript_line(state, "Agente", transcript)
                            await _update_call(
                                db_factory,
                                call_sid=call_sid,
                                transcript_preview="\n".join(state.transcript_lines[-20:]),
                                summary=transcript[:500],
                            )
                        continue

                    # Dispatch tool calls eagerly as each item completes
                    # (instead of waiting for the full response.done)
                    if event_type == "response.output_item.done":
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            try:
                                arguments = json.loads(item.get("arguments") or "{}")
                            except json.JSONDecodeError as exc:
                                json_log(
                                    "app.realtime",
                                    {
                                        "event": "openai_tool_arguments_malformed",
                                        "restaurant_id": restaurant.id,
                                        "call_sid": state.twilio_call_sid,
                                        "tool_name": item.get("name"),
                                        "error": str(exc),
                                        "partial_arguments": item.get("arguments"),
                                    },
                                )
                                continue

                            result = await dispatch_tool(
                                db_factory,
                                restaurant=restaurant,
                                state=state,
                                tool_name=str(item.get("name")),
                                arguments=arguments,
                            )
                            state.tool_events.append(
                                {
                                    "tool": item.get("name"),
                                    "arguments": arguments,
                                    "result": result,
                                }
                            )
                            _record_conversation_turn(
                                state,
                                role="system",
                                text=_format_tool_event_for_summary(str(item.get("name")), result),
                            )
                            await realtime_ws.send(
                                json.dumps(
                                    {
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": item.get("call_id"),
                                            "output": json.dumps(result, ensure_ascii=False),
                                        },
                                    }
                                )
                            )
                            state.pending_tool_followup = True
                            await _sync_tool_scope(
                                realtime_ws,
                                restaurant,
                                state,
                                caller_phone=from_number,
                                output_modalities=("audio",),
                            )
                        elif item.get("type") == "message":
                            message_text = _extract_message_text(item)
                            if message_text:
                                _ingest_assistant_transcript(state, message_text)
                                _record_conversation_turn(
                                    state,
                                    role="assistant",
                                    text=message_text,
                                    item_id=str(item.get("id") or ""),
                                )
                                if _append_transcript_line(state, "Agente", message_text):
                                    await _update_call(
                                        db_factory,
                                        call_sid=call_sid,
                                        transcript_preview="\n".join(state.transcript_lines[-20:]),
                                        summary=message_text[:500],
                                    )
                        continue

                    if event_type == "response.done":
                        hangup_delay_ms = 0
                        if state.end_call_after_response and not state.pending_tool_followup:
                            # Most audio has already been played by the time response.done
                            # arrives, so a short buffer is enough to avoid clipping the
                            # goodbye while still ending the call promptly.
                            hangup_delay_ms = min(max(int((state.last_audio_bytes_sent / 8000) * 120), 400), 1200)
                            state.end_call_after_response = False
                        state.response_in_progress = False
                        state.assistant_is_speaking = False
                        _finish_initial_greeting(state)
                        state.last_audio_item_id = None
                        state.last_audio_content_index = 0
                        state.last_audio_bytes_sent = 0
                        response_payload = event.get("response", {})
                        if response_payload.get("usage"):
                            state.last_response_usage = response_payload["usage"]
                        if (
                            not state.response_audio_started
                            and not state.pending_tool_followup
                            and state.silent_response_retries < MAX_SILENT_RESPONSE_RETRIES
                        ):
                            state.silent_response_retries += 1
                            await _send_response_create(realtime_ws, output_modalities=("audio",))
                            continue
                        await _maybe_refresh_summary(
                            realtime_ws=realtime_ws,
                            db_factory=db_factory,
                            restaurant=restaurant,
                            state=state,
                            call_sid=call_sid,
                        )
                        if state.pending_tool_followup:
                            state.pending_tool_followup = False
                            await _send_response_create(realtime_ws, output_modalities=("audio",))
                        elif hangup_delay_ms and not state.twilio_call_sid.startswith("studio-"):
                            asyncio.create_task(
                                _end_twilio_call_after_delay(
                                    restaurant=restaurant,
                                    call_sid=state.twilio_call_sid,
                                    delay_ms=hangup_delay_ms,
                                )
                            )
                        continue

                    if event_type == "session.updated":
                        json_log(
                            "app.realtime",
                            {
                                "event": "openai_session_updated",
                                "restaurant_id": restaurant.id,
                                "call_sid": call_sid,
                            },
                        )
                        continue

                    if event_type == "rate_limits.updated":
                        json_log(
                            "app.realtime",
                            {
                                "event": "openai_rate_limits",
                                "restaurant_id": restaurant.id,
                                "call_sid": call_sid,
                                "rate_limits": event.get("rate_limits"),
                            },
                        )
                        continue

                    if event_type == "error":
                        error_body = event.get("error", {})
                        error_type = error_body.get("type", "")
                        error_msg = str(error_body.get("message") or error_body or event)
                        if (
                            error_type == "invalid_request_error"
                            and "no active response found" in error_msg.lower()
                        ):
                            state.response_in_progress = False
                            state.assistant_is_speaking = False
                            continue
                        json_log(
                            "app.realtime",
                            {
                                "event": "openai_realtime_error",
                                "restaurant_id": restaurant.id,
                                "call_sid": call_sid,
                                "error_type": error_type,
                                "error": error_msg,
                            },
                        )
                        # Server errors are fatal; input validation errors are recoverable
                        if error_type == "server_error":
                            raise RuntimeError(error_msg)
                        continue

            send_task = asyncio.create_task(twilio_to_openai())
            receive_task = asyncio.create_task(openai_to_twilio())
            done, pending = await asyncio.wait(
                {send_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
    except Exception as exc:
        state.call_status = "failed"
        state.outcome = "tool_error" if state.tool_events else "abandoned"
        transferred = False
        if not state.twilio_call_sid.startswith("studio-"):
            transferred = await asyncio.to_thread(
                _sync_transfer_call_to_restaurant,
                restaurant=restaurant,
                call_sid=state.twilio_call_sid,
            )
            if transferred:
                state.outcome = "escalated"
        await _update_call(
            db_factory,
            call_sid=call_sid,
            provider_call_id=state.openai_session_id or call_sid,
            call_status=state.call_status,
            outcome=state.outcome,
            transcript_preview="\n".join(state.transcript_lines[-20:]),
            summary="Chiamata interrotta per errore realtime.",
            extra_data={
                "openai_session_id": state.openai_session_id,
                "caller_phone": from_number,
                "called_number": to_number,
                "tool_events": state.tool_events,
                "response_usage": state.last_response_usage,
                "transcription_events": state.transcription_events,
                "conversation_summary": state.latest_summary,
                "dropped_input_audio_packets": state.dropped_input_audio_packets,
                "transferred_to_restaurant": transferred,
                "error": str(exc),
            },
            duration_seconds=max(int((datetime.now(UTC) - state.started_at).total_seconds()), 0),
        )
        json_log(
            "app.twilio",
            {
                "event": "twilio_media_stream_failed",
                "restaurant_id": restaurant.id,
                "call_sid": call_sid,
                "provider_call_id": state.openai_session_id,
                "error": str(exc),
            },
        )
        raise

    state.call_status = "successful"
    state.outcome = _successful_call_outcome(state)
    await _update_call(
        db_factory,
        call_sid=call_sid,
        provider_call_id=state.openai_session_id or call_sid,
        call_status=state.call_status,
        outcome=state.outcome,
        transcript_preview="\n".join(state.transcript_lines[-20:]),
        summary=state.transcript_lines[-1][:500] if state.transcript_lines else "Chiamata completata.",
        extra_data={
            "openai_session_id": state.openai_session_id,
            "caller_phone": from_number,
            "called_number": to_number,
            "tool_events": state.tool_events,
            "response_usage": state.last_response_usage,
            "transcription_events": state.transcription_events,
            "conversation_summary": state.latest_summary,
            "dropped_input_audio_packets": state.dropped_input_audio_packets,
        },
        duration_seconds=max(int((datetime.now(UTC) - state.started_at).total_seconds()), 0),
    )
    json_log(
        "app.twilio",
        {
            "event": "twilio_media_stream_completed",
            "restaurant_id": restaurant.id,
            "call_sid": call_sid,
            "provider_call_id": state.openai_session_id,
            "outcome": state.outcome,
        },
    )


async def run_text_simulation(
    *,
    db_factory: sessionmaker,
    restaurant: Restaurant,
    caller_phone: str,
    user_messages: list[str],
    prompt_override: str | None = None,
    overrides: RealtimeSessionOverrides | None = None,
) -> dict[str, Any]:
    if not user_messages:
        return {"assistant_message": "", "transcript": [], "tool_events": [], "usage": None}

    state = RealtimeCallState(caller_phone=caller_phone, twilio_call_sid="studio-sim")
    tuning = merged_session_overrides(restaurant, overrides)
    headers = realtime_headers()
    transcript: list[dict[str, str]] = []
    final_usage: dict[str, Any] | None = None

    async with connect(realtime_ws_url(tuning.model), additional_headers=headers) as realtime_ws:
        await realtime_ws.send(
            json.dumps(
                build_session_update(
                    restaurant,
                    caller_phone=caller_phone,
                    output_modalities=("text",),
                    prompt_override=prompt_override,
                    overrides=overrides,
                    include_diagnostics=True,
                    tool_names=_current_tool_scope(state),
                )
            )
        )
        await _send_runtime_context_message(realtime_ws, restaurant, caller_phone=caller_phone)

        async def run_single_turn(message: str) -> str:
            await realtime_ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": message}],
                        },
                    }
                )
            )
            _ingest_user_transcript(state, message)
            _record_conversation_turn(state, role="user", text=message)
            transcript.append({"role": "user", "content": message})
            await _sync_tool_scope(
                realtime_ws,
                restaurant,
                state,
                caller_phone=caller_phone,
                output_modalities=("text",),
                prompt_override=prompt_override,
                overrides=overrides,
            )
            await _send_response_create(realtime_ws, output_modalities=("text",))

            assistant_chunks: list[str] = []
            pending_tool_followup = False
            while True:
                raw_event = await realtime_ws.recv()
                event = json.loads(raw_event)
                event_type = event.get("type")

                if event_type in {"response.output_text.delta", "response.text.delta"}:
                    delta = str(event.get("delta") or "")
                    if delta:
                        assistant_chunks.append(delta)
                    continue

                if event_type == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        try:
                            arguments = json.loads(item.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            continue

                        result = await dispatch_tool(
                            db_factory,
                            restaurant=restaurant,
                            state=state,
                            tool_name=str(item.get("name")),
                            arguments=arguments,
                        )
                        state.tool_events.append(
                            {
                                "tool": item.get("name"),
                                "arguments": arguments,
                                "result": result,
                            }
                        )
                        await realtime_ws.send(
                            json.dumps(
                                {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": item.get("call_id"),
                                        "output": json.dumps(result, ensure_ascii=False),
                                    },
                                }
                            )
                        )
                        pending_tool_followup = True
                    continue

                if event_type == "response.done":
                    response_payload = event.get("response", {})
                    if pending_tool_followup:
                        pending_tool_followup = False
                        assistant_chunks.clear()
                        await _send_response_create(realtime_ws, output_modalities=("text",))
                        continue
                    text = "".join(assistant_chunks).strip()
                    if not text:
                        text = "Nessuna risposta generata."
                    _ingest_assistant_transcript(state, text)
                    _record_conversation_turn(state, role="assistant", text=text)
                    transcript.append({"role": "assistant", "content": text})
                    nonlocal final_usage
                    final_usage = response_payload.get("usage")
                    return text

                if event_type == "error":
                    raise RuntimeError(str(event.get("error") or event))

        assistant_message = ""
        for message in user_messages:
            assistant_message = await run_single_turn(message)

    return {
        "assistant_message": assistant_message,
        "transcript": transcript,
        "tool_events": state.tool_events,
        "usage": final_usage,
    }
