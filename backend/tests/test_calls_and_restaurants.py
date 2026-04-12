from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.core.config import settings
from app.models import Booking, CallLog, Restaurant
from tests.conftest import login


def test_transcript_endpoint_returns_local_openai_transcript(client, db_session):
    login(client)
    call = db_session.scalar(select(CallLog).where(CallLog.provider_call_id == "rt_demo_1"))

    response = client.get(f"/api/calls/{call.id}/transcript")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "openai_realtime"
    assert "Vorrei un tavolo" in payload["transcript"]


def test_current_restaurant_includes_voice_provider(client):
    login(client)
    response = client.get("/api/restaurants/current")
    assert response.status_code == 200
    payload = response.json()
    assert payload["voice_provider"] == "openai_realtime"


def test_owner_settings_update_returns_local_status_message(client, db_session):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    response = client.patch(
        f"/api/restaurants/{restaurant.id}",
        json={"name": "Trattoria da Mario Nuova"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Trattoria da Mario Nuova"
    assert payload["sync_status"]["synced"] is True
    assert "OpenAI" in payload["sync_status"]["message"]


def test_owner_can_update_assistant_settings(client, db_session):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    response = client.patch(
        f"/api/restaurants/{restaurant.id}",
        json={
            "custom_greeting": "Buonasera, risponde il desk prenotazioni.",
            "agent_style_notes": "Elegant and direct.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["custom_greeting"] == "Buonasera, risponde il desk prenotazioni."
    assert payload["agent_style_notes"] == "Elegant and direct."


def test_operator_can_pause_and_reactivate_restaurant_without_sync(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    paused = client.patch(
        f"/api/restaurants/{restaurant.id}?sync_agent=false",
        json={"is_active": False},
    )
    assert paused.status_code == 200
    assert paused.json()["is_active"] is False

    restored = client.patch(
        f"/api/restaurants/{restaurant.id}?sync_agent=false",
        json={"is_active": True},
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True


def test_operator_duplicate_restaurant_slug_returns_conflict(client):
    login(client, email="operator@ristorante.ai")
    response = client.post(
        "/api/restaurants",
        json={
            "slug": "trattoria-da-mario",
            "name": "Duplicate",
            "address": "Via Test 1",
            "timezone": "Europe/Rome",
            "voice_provider": "openai_realtime",
            "opening_hours": {"lunch": "12:00-15:00"},
            "weekly_closures": [],
            "closure_dates": [],
            "turni": [{"name": "primo", "start": "19:00", "end": "21:00", "max_covers": 20}],
            "booking_rules": {
                "min_party": 1,
                "max_party": 10,
                "large_group_threshold": 6,
                "max_advance_days": 30,
                "min_lead_hours": 2,
            },
            "custom_greeting": None,
            "agent_style_notes": None,
            "is_active": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Restaurant slug already exists"


def test_missing_booking_update_returns_not_found(client):
    login(client)
    response = client.patch(
        "/api/bookings/not-a-real-booking-id",
        json={"special_requests": "Quiet table"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


def test_missing_booking_cancel_returns_not_found(client):
    login(client)
    response = client.post("/api/bookings/not-a-real-booking-id/cancel")
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


def test_tool_create_booking_missing_restaurant_returns_not_found(client):
    response = client.post(
        "/api/tools/create-booking",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={
            "restaurant_id": "missing-restaurant",
            "date": "2026-03-30",
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Bug",
            "customer_phone": "+393331111111",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "ristorante" in data["reason"].lower()


def test_bookings_list_handles_legacy_unreadable_pii_without_crashing(client, db_session):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    first_booking = db_session.scalar(
        select(CallLog.booking_id)
        .where(CallLog.restaurant_id == restaurant.id, CallLog.booking_id.is_not(None))
        .limit(1)
    )
    assert first_booking is not None

    seeded_booking = db_session.scalar(select(Booking).where(Booking.id == first_booking))
    assert seeded_booking is not None
    seeded_booking.customer_name_encrypted = "invalid-fernet-token"
    seeded_booking.customer_phone_encrypted = "invalid-fernet-token"
    db_session.add(seeded_booking)
    db_session.commit()

    response = client.get("/api/bookings", params={"date_from": date.today().isoformat()})
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["customer_name"] == "Dato non disponibile"
    assert payload[0]["customer_phone"] == "****"


def test_twilio_voice_fallback_returns_italian_dial_flow_for_known_restaurant(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    assert restaurant is not None

    response = client.post(
        "/api/twilio/voice-fallback",
        data={
            "Called": restaurant.twilio_phone,
            "From": "+41779802809",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "Ci scusi, stiamo avendo un problema tecnico" in body
    assert f"<Dial>{restaurant.escalation_phone}</Dial>" in body


def test_twilio_voice_fallback_routes_human_when_digit_one_pressed(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    response = client.post(
        "/api/twilio/voice-fallback",
        data={
            "Called": restaurant.twilio_phone,
            "From": "+41779802809",
            "Digits": "1",
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "La metto subito in contatto con il ristorante." in body
    assert f"<Dial>{restaurant.escalation_phone}</Dial>" in body


def test_twilio_voice_fallback_accepts_called_number_without_plus(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.twilio_phone = "+41225394205"
    db_session.add(restaurant)
    db_session.commit()

    response = client.post(
        "/api/twilio/voice-fallback",
        data={
            "Called": "41225394205",
            "From": "+41779802809",
        },
    )

    assert response.status_code == 200
    assert f"<Dial>{restaurant.escalation_phone}</Dial>" in response.text


def test_twilio_voice_fallback_hangs_up_for_unknown_restaurant(client):
    response = client.post(
        "/api/twilio/voice-fallback",
        data={
            "Called": "+41225394205",
            "From": "+41779802809",
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "La invitiamo a richiamare tra qualche minuto." in body
    assert "<Hangup/>" in body


def test_twilio_inbound_returns_openai_media_stream_twiml(client, db_session, monkeypatch):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.twilio_phone = "+41225394205"
    restaurant.voice_provider = "openai_realtime"
    restaurant.custom_greeting = "Buonasera, test realtime."
    restaurant.agent_style_notes = "Supabase QA run."
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.com")
    db_session.add(restaurant)
    db_session.commit()

    response = client.post(
        "/api/twilio/inbound",
        data={
            "From": "+41779802809",
            "To": "+41225394205",
            "CallSid": "CA_test_real_ai",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "<Gather" not in body
    assert "<Connect>" in body
    assert "<Stream" in body
    assert "twilio/media-stream" in body
    assert "<Parameter name=\"token\"" in body
    assert 'statusCallback="https://api.example.com/api/twilio/status"' in body


def test_twilio_inbound_accepts_to_number_without_plus(client, db_session, monkeypatch):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.twilio_phone = "+41225394205"
    restaurant.voice_provider = "openai_realtime"
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.com")
    db_session.add(restaurant)
    db_session.commit()

    response = client.post(
        "/api/twilio/inbound",
        data={
            "From": "+41779802809",
            "To": "41225394205",
            "CallSid": "CA_test_without_plus",
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "<Connect>" in body
    assert "<Stream" in body
    assert "Ci scusi, stiamo avendo un problema tecnico" not in body


def test_twilio_inbound_falls_back_when_restaurant_is_missing(client):
    response = client.post(
        "/api/twilio/inbound",
        data={
            "From": "+41779802809",
            "To": "+41225394205",
            "CallSid": "CA_test_failover",
        },
    )

    assert response.status_code == 200
    assert "Ci scusi, stiamo avendo un problema tecnico" in response.text


def test_twilio_status_callback_records_stream_errors(client, db_session):
    call = CallLog(
        restaurant_id=db_session.scalar(select(Restaurant.id).where(Restaurant.slug == "trattoria-da-mario")),
        voice_provider="openai_realtime",
        provider_call_id="rt_stream_error",
        twilio_call_sid="CA_stream_error",
        started_at=datetime.now(UTC),
        duration_seconds=0,
        outcome="info_provided",
        call_status="unknown",
        summary="",
        transcript_preview="",
        extra_data={},
    )
    db_session.add(call)
    db_session.commit()

    response = client.post(
        "/api/twilio/status",
        data={
            "CallSid": "CA_stream_error",
            "StreamSid": "MZ123",
            "StreamEvent": "stream-error",
            "StreamError": "websocket closed",
        },
    )

    assert response.status_code == 200
    db_session.refresh(call)
    assert call.call_status == "failed"
    assert call.extra_data["twilio_stream_event"] == "stream-error"
    assert call.extra_data["twilio_stream_error"] == "websocket closed"


def test_twilio_stream_status_without_call_status_preserves_existing_status(client, db_session):
    call = CallLog(
        restaurant_id=db_session.scalar(select(Restaurant.id).where(Restaurant.slug == "trattoria-da-mario")),
        voice_provider="openai_realtime",
        provider_call_id="rt_stream_completed",
        twilio_call_sid="CA_stream_completed",
        started_at=datetime.now(UTC),
        duration_seconds=12,
        outcome="booking_created",
        call_status="successful",
        summary="Chiamata completata.",
        transcript_preview="Preview locale.",
        extra_data={},
    )
    db_session.add(call)
    db_session.commit()

    response = client.post(
        "/api/twilio/status",
        data={
            "CallSid": "CA_stream_completed",
            "StreamSid": "MZ456",
            "StreamEvent": "stream-stopped",
        },
    )

    assert response.status_code == 200
    db_session.refresh(call)
    assert call.call_status == "successful"
    assert call.extra_data["twilio_stream_event"] == "stream-stopped"


def test_calls_list_reads_local_db_only(client):
    login(client)
    response = client.get("/api/calls")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert payload[0]["voice_provider"] == "openai_realtime"


def test_calls_list_supports_search_attention_and_sort(client, db_session):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    long_call = CallLog(
        restaurant_id=restaurant.id,
        voice_provider="openai_realtime",
        provider_call_id="rt_longest",
        twilio_call_sid="CA_longest",
        started_at=datetime.now(UTC),
        duration_seconds=420,
        outcome="info_provided",
        call_status="successful",
        summary="Cliente chiede informazioni su un compleanno.",
        transcript_preview="Servono dettagli per un compleanno sabato.",
        extra_data={},
    )
    follow_up_call = CallLog(
        restaurant_id=restaurant.id,
        voice_provider="openai_realtime",
        provider_call_id="rt_followup",
        twilio_call_sid="CA_followup",
        started_at=datetime.now(UTC),
        duration_seconds=35,
        outcome="tool_error",
        call_status="failed",
        summary="Errore tecnico durante la richiesta.",
        transcript_preview="Il tool availability non ha risposto.",
        extra_data={},
    )
    db_session.add_all([long_call, follow_up_call])
    db_session.commit()

    search_response = client.get("/api/calls", params={"search": "compleanno"})
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload
    assert all(
        "compleanno" in f"{item['summary']} {item.get('transcript_preview') or ''}".lower()
        for item in search_payload
    )

    attention_response = client.get("/api/calls", params={"attention_only": "true"})
    assert attention_response.status_code == 200
    attention_payload = attention_response.json()
    assert attention_payload
    assert all(
        item["call_status"] == "failed" or item["outcome"] in {"tool_error", "abandoned"}
        for item in attention_payload
    )

    longest_response = client.get("/api/calls", params={"sort": "longest"})
    assert longest_response.status_code == 200
    longest_payload = longest_response.json()
    assert longest_payload[0]["provider_call_id"] == "rt_longest"

    follow_up_response = client.get("/api/calls", params={"sort": "follow_up"})
    assert follow_up_response.status_code == 200
    follow_up_payload = follow_up_response.json()
    assert follow_up_payload[0]["provider_call_id"] == "rt_followup"


def test_owner_agenda_returns_seven_day_turno_board(client, db_session):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.weekly_closures = ["monday"]
    restaurant.closure_dates = ["2099-12-31"]
    db_session.add(restaurant)
    db_session.commit()

    response = client.get("/api/owner/agenda", params={"days": 7})
    assert response.status_code == 200
    payload = response.json()
    assert payload["restaurant_id"] == restaurant.id
    assert len(payload["days"]) == 7
    assert {"today_booked_covers", "today_calls", "today_unresolved_calls"} <= payload["summary"].keys()
    assert payload["days"][0]["turni"]
    first_turno = payload["days"][0]["turni"][0]
    assert {
        "turno",
        "booked_covers",
        "booking_count",
        "max_covers",
        "remaining_covers",
        "occupancy_ratio",
        "fullness",
    } <= first_turno.keys()


def test_call_sync_endpoint_returns_local_noop_counts(client):
    login(client)
    response = client.post("/api/calls/sync")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "replayed_events": 0,
        "failed_events": 0,
        "pending_events": 0,
        "backfilled_calls": 0,
    }


def test_call_sync_endpoint_is_owner_only(client):
    login(client, email="operator@ristorante.ai")
    response = client.post("/api/calls/sync")
    assert response.status_code == 403


def test_status_callback_marks_call_failed(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    call = CallLog(
        restaurant_id=restaurant.id,
        voice_provider="openai_realtime",
        provider_call_id="rt_status_test",
        twilio_call_sid="CA_status_test",
        started_at=datetime.now(UTC),
        duration_seconds=10,
        outcome="info_provided",
        call_status="unknown",
        summary="In corso.",
        transcript_preview="Preview locale.",
        extra_data={},
    )
    db_session.add(call)
    db_session.commit()

    response = client.post(
        "/api/twilio/status",
        data={
            "CallSid": "CA_status_test",
            "CallStatus": "failed",
            "CallDuration": "14",
        },
    )

    assert response.status_code == 200
    db_session.refresh(call)
    assert call.call_status == "failed"
    assert call.duration_seconds == 14
