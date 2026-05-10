from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlparse

from sqlalchemy import select, text

from app.models import Booking, Restaurant

TOOL_HEADERS = {"X-Ristorante-Tool-Secret": "local-tool-secret"}


def _next_open_date(offset: int = 0) -> str:
    candidate = date.today() + timedelta(days=5)
    skipped = 0
    while True:
        if candidate.strftime("%A").lower() != "monday":
            if skipped == offset:
                return candidate.isoformat()
            skipped += 1
        candidate += timedelta(days=1)


def _restaurant(db_session) -> Restaurant:
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    assert restaurant is not None
    return restaurant


def _booking_payload() -> dict[str, object]:
    return {
        "date": _next_open_date(),
        "time": "20:00:00",
        "party_size": 2,
        "customer_name": "Giulia Verdi",
        "customer_phone": "+393331234890",
        "customer_email": "giulia@example.com",
        "special_requests": "Tavolo vicino alla finestra",
    }


def test_public_reservation_config_exposes_online_settings(client, db_session) -> None:
    restaurant = _restaurant(db_session)

    response = client.get(f"/api/public/restaurants/{restaurant.slug}/reservation-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["restaurant"]["slug"] == restaurant.slug
    assert payload["online_booking"]["enabled"] is True
    assert payload["online_booking"]["party_size_min"] == 1
    assert payload["online_booking"]["party_size_max"] == 8
    assert payload["online_booking"]["modify_cutoff_hours"] >= 0
    assert payload["online_booking"]["cancel_cutoff_hours"] >= 0


def test_public_booking_create_is_idempotent_and_visible_to_ai_tools(client, db_session) -> None:
    restaurant = _restaurant(db_session)
    payload = _booking_payload()

    first = client.post(
        f"/api/public/restaurants/{restaurant.slug}/bookings",
        headers={"Idempotency-Key": "public-create-001"},
        json=payload,
    )
    assert first.status_code == 201, first.text
    first_payload = first.json()

    second = client.post(
        f"/api/public/restaurants/{restaurant.slug}/bookings",
        headers={"Idempotency-Key": "public-create-001"},
        json=payload,
    )
    assert second.status_code == 200, second.text
    second_payload = second.json()

    assert first_payload["booking"]["id"] == second_payload["booking"]["id"]
    assert first_payload["booking"]["source"] == "web"
    assert first_payload["booking"]["customer_email"] == "giulia@example.com"
    assert first_payload["manage_url"]

    booking_count = db_session.execute(
        text("SELECT count(*) FROM bookings WHERE source = 'web'")
    ).scalar_one()
    assert booking_count == 1

    token_count = db_session.execute(
        text("SELECT count(*) FROM booking_guest_tokens")
    ).scalar_one()
    assert token_count == 1

    outbox_count = db_session.execute(
        text("SELECT count(*) FROM notification_outbox WHERE template_key = 'booking_confirmation'")
    ).scalar_one()
    assert outbox_count == 1

    find_response = client.post(
        "/api/tools/find-booking",
        headers=TOOL_HEADERS,
        json={
            "restaurant_id": restaurant.id,
            "caller_phone": payload["customer_phone"],
        },
    )
    assert find_response.status_code == 200
    assert find_response.json()["found"] is True


def test_public_manage_token_can_view_modify_and_cancel_booking(client, db_session) -> None:
    restaurant = _restaurant(db_session)
    create_response = client.post(
        f"/api/public/restaurants/{restaurant.slug}/bookings",
        headers={"Idempotency-Key": "public-create-002"},
        json=_booking_payload(),
    )
    assert create_response.status_code == 201, create_response.text
    create_payload = create_response.json()
    manage_path = urlparse(create_payload["manage_url"]).path
    manage_token = manage_path.rstrip("/").split("/")[-1]

    detail_response = client.get(f"/api/public/bookings/{manage_token}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["booking"]["status"] == "confirmed"
    assert detail_payload["booking"]["customer_email"] == "giulia@example.com"

    modify_response = client.post(
        f"/api/public/bookings/{manage_token}/modify",
        json={
            "date": _next_open_date(1),
            "time": "21:00:00",
            "party_size": 4,
            "special_requests": "Serve seggiolone",
        },
    )
    assert modify_response.status_code == 200, modify_response.text
    assert modify_response.json()["booking"]["party_size"] == 4
    assert modify_response.json()["booking"]["status"] == "modified"

    cancel_response = client.post(f"/api/public/bookings/{manage_token}/cancel")
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["booking"]["status"] == "cancelled"

    templates = db_session.execute(
        text(
            "SELECT template_key FROM notification_outbox "
            "WHERE booking_id = :booking_id ORDER BY created_at ASC"
        ),
        {"booking_id": create_payload["booking"]["id"]},
    ).scalars().all()
    assert templates == [
        "booking_confirmation",
        "booking_modified",
        "booking_cancelled",
    ]

    booking = db_session.get(Booking, create_payload["booking"]["id"])
    assert booking is not None
    assert booking.status == "cancelled"
