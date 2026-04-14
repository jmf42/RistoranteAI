from __future__ import annotations

from sqlalchemy import select

from app.api.deps import get_restaurant_cached
from app.models import Restaurant
from tests.conftest import login


def test_operator_can_preview_realtime_agent_blueprint(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    response = client.get("/api/studio/agent", params={"restaurant_id": restaurant.id})

    assert response.status_code == 200
    payload = response.json()
    assert "Role & Objective" in payload["prompt"]
    assert payload["session_update"]["type"] == "session.update"
    assert payload["tools"]
    assert payload["checklist"]
    assert payload["readiness"]
    assert payload["prompt_diagnostics"]
    assert payload["recommendations"]
    assert payload["config_diff"]
    assert payload["presets"]
    assert payload["scenarios"]
    assert payload["effective_session_overrides"]["model"] == "gpt-realtime-1.5"
    assert payload["session_update"]["session"]["type"] == "realtime"
    assert "Apri in italiano solo come default iniziale" in payload["prompt"]
    assert "cambia SOLO la lingua della risposta" in payload["prompt"]
    assert "language" not in payload["session_update"]["session"]["audio"]["input"]["transcription"]
    recommendation_labels = {item["label"] for item in payload["recommendations"]}
    assert "Flexible input language" in recommendation_labels


def test_operator_tool_sandbox_respects_runtime_tool_scope(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    response = client.post(
        "/api/studio/tool-test",
        json={
            "restaurant_id": restaurant.id,
            "tool_name": "create_booking",
            "arguments": {
                "date": "2026-04-10",
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Luca",
            },
            "caller_phone": "+393491112233",
            "last_user_transcript": "sì",
            "last_assistant_transcript": "Per che giorno, a che ora e per quante persone?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["success"] is False
    assert "Tool non disponibile" in payload["result"]["reason"]


def test_operator_can_run_realtime_text_simulation(client, db_session, monkeypatch):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    async def fake_simulation(**_: object) -> dict[str, object]:
        return {
            "assistant_message": "Perfetto, verifico subito.",
            "transcript": [
                {"role": "user", "content": "Vorrei prenotare per due."},
                {"role": "assistant", "content": "Perfetto, verifico subito."},
            ],
            "tool_events": [{"tool": "check_availability", "result": {"available": True}}],
            "usage": {"total_tokens": 123},
        }

    monkeypatch.setattr("app.api.studio.run_text_simulation", fake_simulation)

    response = client.post(
        "/api/studio/simulate",
        json={
            "restaurant_id": restaurant.id,
            "caller_phone": "+393491112233",
            "user_messages": ["Vorrei prenotare per due."],
            "prompt_override": "Prompt di test",
            "session_overrides": {"voice": "marin", "tool_choice": "auto"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_message"] == "Perfetto, verifico subito."
    assert payload["transcript"][0]["role"] == "user"
    assert payload["tool_events"][0]["tool"] == "check_availability"


def test_operator_can_save_and_reset_persistent_studio_config(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    save_response = client.put(
        "/api/studio/config",
        json={
            "restaurant_id": restaurant.id,
            "prompt_override": "Prompt di produzione personalizzato",
            "session_overrides": {
                "model": "gpt-realtime-1.5",
                "voice": "cedar",
                "tool_choice": "auto",
                "max_response_output_tokens": 180,
            },
        },
    )

    assert save_response.status_code == 200
    save_payload = save_response.json()
    assert save_payload["deployed"] is True
    assert save_payload["deployment_status"] == "warning"
    assert save_payload["effective_prompt"] == "Prompt di produzione personalizzato"
    assert save_payload["effective_prompt_hash"]
    assert save_payload["effective_session_overrides"]["voice"] == "cedar"
    assert isinstance(save_payload["prompt_diagnostics"], list)
    assert save_payload["published_at"]
    db_session.refresh(restaurant)
    assert restaurant.openai_prompt_override == "Prompt di produzione personalizzato"
    assert restaurant.openai_realtime_settings["model"] == "gpt-realtime-1.5"
    assert restaurant.openai_realtime_settings["voice"] == "cedar"
    assert "max_response_output_tokens" not in restaurant.openai_realtime_settings
    assert "tool_choice" not in restaurant.openai_realtime_settings

    preview_response = client.get("/api/studio/agent", params={"restaurant_id": restaurant.id})
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["saved_prompt_override"] == "Prompt di produzione personalizzato"
    assert preview_payload["saved_session_overrides"]["model"] == "gpt-realtime-1.5"
    assert preview_payload["session_update"]["session"]["model"] == "gpt-realtime-1.5"
    assert preview_payload["session_update"]["session"]["audio"]["output"]["voice"] == "cedar"
    assert isinstance(preview_payload["config_diff"], list)

    reset_response = client.delete("/api/studio/config", params={"restaurant_id": restaurant.id})
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["deployed"] is True
    assert reset_payload["deployment_status"] in {"live", "warning"}
    assert "Role & Objective" in reset_payload["effective_prompt"]
    assert reset_payload["effective_prompt_hash"]
    db_session.refresh(restaurant)
    assert restaurant.openai_prompt_override is None
    assert restaurant.openai_realtime_settings == {}


def test_studio_config_save_invalidates_restaurant_cache(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))

    warmed = get_restaurant_cached(db_session, restaurant.id)
    assert warmed.openai_prompt_override is None

    response = client.put(
        "/api/studio/config",
        json={
            "restaurant_id": restaurant.id,
            "prompt_override": "Prompt aggiornato subito",
            "session_overrides": {"voice": "cedar"},
        },
    )

    assert response.status_code == 200

    db_session.expire_all()
    refreshed = get_restaurant_cached(db_session, restaurant.id)
    assert refreshed.openai_prompt_override == "Prompt aggiornato subito"
    assert refreshed.openai_realtime_settings["voice"] == "cedar"


def test_studio_publish_response_matches_cached_runtime_prompt(client, db_session):
    login(client, email="operator@ristorante.ai")
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    prompt = (
        "Role & Objective\n"
        "- Prompt live verificato\n\n"
        "Language\n"
        "- Italiano.\n\n"
        "Tools\n"
        "- Controllo subito.\n\n"
        "Write Action Rules\n"
        "- Conferma esplicita in turno separato.\n\n"
        "Safety & Escalation\n"
        "- La metto in contatto con il ristorante.\n\n"
        "Unclear Audio\n"
        "- Non inventare."
    )

    response = client.put(
        "/api/studio/config",
        json={
            "restaurant_id": restaurant.id,
            "prompt_override": prompt,
            "session_overrides": {"voice": "marin"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    cached = get_restaurant_cached(db_session, restaurant.id)
    assert payload["effective_prompt"] == cached.openai_prompt_override
    assert payload["effective_session_overrides"]["voice"] == "marin"
