from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, Restaurant
from app.schemas.restaurant import RestaurantCreate
from tests.conftest import login


def _next_open_date(offset: int = 0) -> str:
    candidate = date.today() + timedelta(days=5 + offset)
    while candidate.strftime("%A").lower() == "monday":
        candidate += timedelta(days=1)
    return candidate.isoformat()


def _restaurant_id(db_session: Session) -> str:
    restaurant = db_session.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))
    assert restaurant is not None
    return restaurant.id


def test_healthz_includes_request_id(client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_readyz_responds_ok(client) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_opening_hours_rejects_end_before_start() -> None:
    try:
        RestaurantCreate(
            slug="bad-hours",
            name="Bad Hours",
            address="Via Test 1",
            opening_hours={"dinner": "23:00-19:00"},
        )
    except Exception as exc:  # noqa: BLE001
        assert "start must be earlier than end" in str(exc)
    else:
        raise AssertionError("Expected invalid opening hours to be rejected")


def test_turni_reject_end_before_start() -> None:
    try:
        RestaurantCreate(
            slug="bad-turno",
            name="Bad Turno",
            address="Via Test 1",
            turni=[{"name": "primo", "start": "21:00", "end": "19:00", "max_covers": 10}],
        )
    except Exception as exc:  # noqa: BLE001
        assert "start' must be earlier than 'end'" in str(exc)
    else:
        raise AssertionError("Expected invalid turno ordering to be rejected")


def test_booking_events_endpoint_returns_audit_history(client, db_session: Session) -> None:
    login(client)
    restaurant_id = _restaurant_id(db_session)
    response = client.post(
        "/api/bookings",
        json={
            "restaurant_id": restaurant_id,
            "date": _next_open_date(),
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Event Test",
            "customer_phone": "+393331234560",
        },
    )
    assert response.status_code == 201
    booking_id = response.json()["id"]

    events_response = client.get(f"/api/bookings/{booking_id}/events")
    assert events_response.status_code == 200
    payload = events_response.json()
    assert len(payload) == 1
    assert payload[0]["event_type"] == "created"


def test_bookings_export_returns_csv(client, db_session: Session) -> None:
    login(client)
    restaurant_id = _restaurant_id(db_session)
    response = client.get(
        f"/api/bookings/export?restaurant_id={restaurant_id}&date_from={_next_open_date()}"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "confirmation_code" in response.text


def test_calls_export_returns_csv(client, db_session: Session) -> None:
    login(client)
    restaurant_id = _restaurant_id(db_session)
    response = client.get(f"/api/calls/export?restaurant_id={restaurant_id}&days=30")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "duration_seconds" in response.text


def test_operator_can_modify_booking_with_selected_restaurant(client, db_session: Session) -> None:
    restaurant_id = _restaurant_id(db_session)
    login(client)
    create_response = client.post(
        "/api/bookings",
        json={
            "restaurant_id": restaurant_id,
            "date": _next_open_date(),
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": "Owner Create",
            "customer_phone": "+393331234561",
        },
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]

    login(client, email="operator@ristorante.ai")
    response = client.patch(
        f"/api/bookings/{booking_id}?restaurant_id={restaurant_id}",
        json={"party_size": 4},
    )
    assert response.status_code == 200
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    assert booking.party_size == 4


def test_operator_can_cancel_booking_with_selected_restaurant(client, db_session: Session) -> None:
    restaurant_id = _restaurant_id(db_session)
    login(client)
    create_response = client.post(
        "/api/bookings",
        json={
            "restaurant_id": restaurant_id,
            "date": _next_open_date(1),
            "time": "21:00:00",
            "party_size": 2,
            "customer_name": "Owner Cancel",
            "customer_phone": "+393331234562",
        },
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]

    login(client, email="operator@ristorante.ai")
    response = client.post(f"/api/bookings/{booking_id}/cancel?restaurant_id={restaurant_id}")
    assert response.status_code == 200
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    assert booking.status == "cancelled"

