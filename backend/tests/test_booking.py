from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models import Restaurant
from tests.conftest import login


def test_create_booking_via_dashboard(client):
    login(client)
    restaurant_id = client.get("/api/restaurants/current").json()["id"]
    response = client.post(
        "/api/bookings",
        json={
            "restaurant_id": restaurant_id,
            "date": (date.today() + timedelta(days=3)).isoformat(),
            "time": "20:00:00",
            "party_size": 3,
            "customer_name": "Verdi",
            "customer_phone": "+393339991111",
            "special_requests": "Tavolo tranquillo",
            "source": "dashboard",
            "status": "confirmed",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["customer_name"] == "Verdi"
    assert payload["confirmation_code"].startswith("TD")


def test_tool_booking_flow(client, db_session):
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    create_response = client.post(
        "/api/tools/create-booking",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={
            "restaurant_id": restaurant.id,
            "date": (date.today() + timedelta(days=4)).isoformat(),
            "time": "21:00:00",
            "party_size": 2,
            "customer_name": "Neri",
            "customer_phone": "+393330000000",
            "caller_phone": "+393330000000",
            "special_requests": "Allergia noci",
        },
    )
    assert create_response.status_code == 200
    confirmation_code = create_response.json()["confirmation_code"]

    find_response = client.post(
        "/api/tools/find-booking",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={"restaurant_id": restaurant.id, "confirmation_code": confirmation_code},
    )
    assert find_response.status_code == 200
    assert find_response.json()["found"] is True

    modify_response = client.post(
        "/api/tools/modify-booking",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={
            "confirmation_code": confirmation_code,
            "changes": {"time": "21:15:00"},
        },
    )
    assert modify_response.status_code == 200
    assert modify_response.json()["success"] is True

    cancel_response = client.post(
        "/api/tools/cancel-booking",
        headers={"X-Ristorante-Tool-Secret": "local-tool-secret"},
        json={"confirmation_code": confirmation_code},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["success"] is True
