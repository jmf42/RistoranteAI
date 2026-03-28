from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.integrations.elevenlabs import SyncResult, elevenlabs_service
from app.models import Booking, CallLog, Restaurant
from tests.conftest import login


def test_transcript_endpoint_returns_local_preview_when_remote_unavailable(client, db_session, monkeypatch):
    login(client)
    call = db_session.scalar(select(CallLog).where(CallLog.elevenlabs_conversation_id == "conv_demo_1"))

    monkeypatch.setattr(elevenlabs_service, "fetch_conversation_transcript", lambda _: None)

    response = client.get(f"/api/calls/{call.id}/transcript")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local-preview"
    assert "Vorrei un tavolo" in payload["transcript"]


def test_transcript_endpoint_uses_selected_restaurant_for_operator_access(client, db_session, monkeypatch):
    login(client, email="operator@ristorante.ai")
    second_restaurant = Restaurant(
        slug="osteria-notturna",
        name="Osteria Notturna",
        address="Via Po 10, Torino",
        timezone="Europe/Rome",
        turni=[{"name": "serale", "start": "20:00", "end": "23:00", "max_covers": 24}],
        booking_rules={
            "min_party": 1,
            "max_party": 10,
            "large_group_threshold": 6,
            "max_advance_days": 30,
            "min_lead_hours": 2,
        },
    )
    db_session.add(second_restaurant)
    db_session.flush()
    call = CallLog(
        restaurant_id=second_restaurant.id,
        elevenlabs_conversation_id="conv_remote_operator",
        started_at=datetime.now(UTC),
        duration_seconds=65,
        outcome="info_provided",
        summary="Chiamata di prova per operatore.",
        transcript_preview="Preview locale di fallback.",
        extra_data={},
    )
    db_session.add(call)
    db_session.commit()

    monkeypatch.setattr(
        elevenlabs_service,
        "fetch_conversation_transcript",
        lambda _: {
            "transcript": "User: Buonasera.\nAgent: Benvenuti.",
            "analysis": {"transcript_summary": "Transcript remoto completo."},
            "status": "done",
            "metadata": {"called_number": "+390111111111"},
        },
    )

    response = client.get(f"/api/calls/{call.id}/transcript?restaurant_id={second_restaurant.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "elevenlabs"
    assert payload["summary"] == "Transcript remoto completo."
    assert "Benvenuti" in payload["transcript"]


def test_owner_settings_update_returns_sync_status(client, db_session, monkeypatch):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    monkeypatch.setattr(
        elevenlabs_service,
        "sync_restaurant_config",
        lambda _: SyncResult(synced=True, message="ElevenLabs agent synced successfully: display name updated."),
    )

    response = client.patch(
        f"/api/restaurants/{restaurant.id}",
        json={"name": "Trattoria da Mario Nuova"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Trattoria da Mario Nuova"
    assert payload["sync_status"]["synced"] is True


def test_owner_can_update_assistant_settings(client, db_session, monkeypatch):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    monkeypatch.setattr(
        elevenlabs_service,
        "sync_restaurant_config",
        lambda _: SyncResult(synced=True, message="Agent verified."),
    )

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


def test_personalization_includes_assistant_settings(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.custom_greeting = "Buonasera, benvenuti da Mario."
    restaurant.agent_style_notes = "Elegant and direct."
    db_session.add(restaurant)
    db_session.commit()

    response = client.post(
        "/api/integrations/elevenlabs/twilio-personalization",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={
            "caller_id": "+393331234567",
            "agent_id": restaurant.elevenlabs_agent_id,
            "called_number": restaurant.twilio_phone,
            "call_sid": "CA-demo"
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dynamic_variables"]["agent_style_notes"] == "Elegant and direct."
    assert payload["dynamic_variables"]["greeting"] == "Buonasera, benvenuti da Mario."
    assert payload.get("conversation_config_override") is None


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
    assert response.status_code == 404
    assert response.json()["detail"] == "Restaurant not found"


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
    # Phone is masked in list views; fallback text has no digits → "****"
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


def test_twilio_inbound_registers_real_ai_call(client, db_session, monkeypatch):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.twilio_phone = "+41225394205"
    restaurant.elevenlabs_agent_id = "agent_9801kmkb15jhfnn8m2k99kqb3wps"
    restaurant.custom_greeting = "Buonasera, test Supabase."
    restaurant.agent_style_notes = "Supabase QA run."
    db_session.add(restaurant)
    db_session.commit()

    captured = {}

    def fake_register_twilio_call(**kwargs):
        captured.update(kwargs)
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Connect /></Response>"

    monkeypatch.setattr(elevenlabs_service, "register_twilio_call", fake_register_twilio_call)

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
    assert "<Connect" in response.text
    assert captured["agent_id"] == "agent_9801kmkb15jhfnn8m2k99kqb3wps"
    assert captured["from_number"] == "+41779802809"
    assert captured["to_number"] == "+41225394205"
    client_data = captured["conversation_initiation_client_data"]
    assert client_data["type"] == "conversation_initiation_client_data"
    assert client_data["dynamic_variables"]["restaurant_name"] == "Trattoria da Mario"
    assert "greeting" in client_data["dynamic_variables"]


def test_twilio_inbound_falls_back_when_register_call_fails(client, db_session, monkeypatch):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    restaurant.twilio_phone = "+41225394205"
    restaurant.elevenlabs_agent_id = "agent_9801kmkb15jhfnn8m2k99kqb3wps"
    db_session.add(restaurant)
    db_session.commit()

    monkeypatch.setattr(
        elevenlabs_service,
        "register_twilio_call",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )

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


def test_calls_list_backfills_missing_elevenlabs_twilio_calls(client, db_session, monkeypatch):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    assert restaurant is not None

    monkeypatch.setattr(
        elevenlabs_service,
        "list_recent_conversations",
        lambda **_: [
            {
                "conversation_id": "conv_missing_from_webhook",
                "conversation_initiation_source": "twilio",
                "direction": "inbound",
            },
            {
                "conversation_id": "conv_browser_test",
                "conversation_initiation_source": "react_sdk",
                "direction": None,
            },
        ],
    )
    monkeypatch.setattr(
        elevenlabs_service,
        "fetch_conversation",
        lambda conversation_id: {
            "conversation_id": conversation_id,
            "agent_id": restaurant.elevenlabs_agent_id,
            "status": "done",
            "call_successful": "failure",
            "transcript": [{"role": "agent", "message": "Mi scusi, ho avuto un problema tecnico."}],
            "analysis": {"transcript_summary": "Tentativo prenotazione non completato."},
            "metadata": {
                "start_time_unix_secs": 1774706210,
                "call_duration_secs": 118,
                "phone_call": {
                    "direction": "inbound",
                    "agent_number": restaurant.twilio_phone,
                    "external_number": "+41779802809",
                },
            },
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "restaurant_id": restaurant.id,
                    "called_number": restaurant.twilio_phone,
                    "caller_phone": "+41779802809",
                }
            },
        },
    )

    response = client.get("/api/calls")
    assert response.status_code == 200
    payload = response.json()
    synced = next(item for item in payload if item["elevenlabs_conversation_id"] == "conv_missing_from_webhook")
    assert synced["call_status"] == "failed"
    assert synced["outcome"] == "info_provided"

    stored = db_session.scalar(
        select(CallLog).where(CallLog.elevenlabs_conversation_id == "conv_missing_from_webhook")
    )
    assert stored is not None
    assert stored.call_status == "failed"


def test_calls_list_backfill_marks_tool_error_when_remote_transcript_shows_failure(
    client, db_session, monkeypatch
):
    login(client)
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    assert restaurant is not None

    monkeypatch.setattr(
        elevenlabs_service,
        "list_recent_conversations",
        lambda **_: [
            {
                "conversation_id": "conv_tool_error",
                "conversation_initiation_source": "twilio",
                "direction": "inbound",
            }
        ],
    )
    monkeypatch.setattr(
        elevenlabs_service,
        "fetch_conversation",
        lambda conversation_id: {
            "conversation_id": conversation_id,
            "agent_id": restaurant.elevenlabs_agent_id,
            "status": "done",
            "call_successful": "failure",
            "transcript": "Tool failed while creating reservation.",
            "analysis": {"transcript_summary": "La prenotazione non è andata a buon fine."},
            "metadata": {
                "start_time_unix_secs": 1774706210,
                "call_duration_secs": 45,
                "phone_call": {
                    "direction": "inbound",
                    "agent_number": restaurant.twilio_phone,
                    "external_number": "+41779802809",
                },
            },
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "restaurant_id": restaurant.id,
                    "called_number": restaurant.twilio_phone,
                    "caller_phone": "+41779802809",
                }
            },
        },
    )

    response = client.get("/api/calls")
    assert response.status_code == 200
    payload = response.json()
    synced = next(item for item in payload if item["elevenlabs_conversation_id"] == "conv_tool_error")
    assert synced["outcome"] == "tool_error"
