"""End-to-end lifecycle tests — simulates real restaurant operations:
create bookings, modify them, cancel, verify customer stats, audit trail,
capacity changes, and settings round-trips."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingEvent, Customer, Restaurant
from tests.conftest import login

CLOSED_WEEKDAY = "monday"
TOOL_HEADERS = {"X-Ristorante-Tool-Secret": "local-tool-secret"}


def _next_open_date(offset: int = 0) -> str:
    candidate = date.today() + timedelta(days=5 + offset)
    while candidate.strftime("%A").lower() == CLOSED_WEEKDAY:
        candidate += timedelta(days=1)
    return candidate.isoformat()


DATE_1 = _next_open_date(0)
DATE_2 = _next_open_date(1)
DATE_3 = _next_open_date(2)


def _restaurant(db: Session) -> Restaurant:
    return db.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))


# ===========================================================================
# 1. Full booking lifecycle: create → modify → cancel → verify everything
# ===========================================================================


class TestFullBookingLifecycle:
    """Simulates a real customer calling, booking a table, changing the party
    size, then cancelling — and verifies every side-effect."""

    def test_lifecycle_via_ai_phone(self, client: TestClient, db_session: Session):
        r = _restaurant(db_session)
        phone = "+393401234567"

        # --- Step 1: Create booking via AI phone call ---
        resp = client.post(
            "/api/tools/create-booking",
            headers=TOOL_HEADERS,
            json={
                "restaurant_id": r.id,
                "date": DATE_1,
                "time": "20:30:00",
                "party_size": 4,
                "customer_name": "Giovanni Bianchi",
                "customer_phone": phone,
                "caller_phone": phone,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        code = data["confirmation_code"]

        # Verify booking exists
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == code)
        )
        assert booking is not None
        assert booking.party_size == 4
        assert booking.status == "confirmed"
        assert booking.source == "ai_phone"
        assert booking.customer_id is not None

        # Verify customer created
        customer = db_session.get(Customer, booking.customer_id)
        assert customer is not None
        assert customer.booking_count == 1
        assert customer.cancellation_count == 0

        # Verify audit event
        events = db_session.scalars(
            select(BookingEvent).where(BookingEvent.booking_id == booking.id)
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].changed_by == "ai_phone"

        # --- Step 2: Modify booking (change party_size) ---
        resp = client.post(
            "/api/tools/modify-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code, "changes": {"party_size": 6}},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        db_session.expire_all()
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == code)
        )
        assert booking.party_size == 6
        assert booking.status == "modified"

        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        assert len(events) == 2
        mod_event = events[1]
        assert mod_event.event_type == "modified"
        assert mod_event.changes["party_size"]["from"] == 4
        assert mod_event.changes["party_size"]["to"] == 6

        # --- Step 3: Cancel booking ---
        resp = client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == code)
        )
        assert booking.status == "cancelled"

        # Verify cancellation event logged
        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        assert len(events) == 3
        assert events[2].event_type == "cancelled"

        # Verify customer cancellation count incremented
        customer = db_session.get(Customer, booking.customer_id)
        assert customer.cancellation_count == 1
        assert customer.booking_count == 1  # still 1, cancellation doesn't decrement

    def test_lifecycle_via_dashboard(self, client: TestClient, db_session: Session):
        """Same lifecycle but from the dashboard UI perspective."""
        login(client)
        r = _restaurant(db_session)

        # --- Create ---
        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": r.id,
                "date": DATE_1,
                "time": "21:00:00",
                "party_size": 2,
                "customer_name": "Maria Verdi",
                "customer_phone": "+393409876543",
            },
        )
        assert resp.status_code == 201
        booking_data = resp.json()
        booking_id = booking_data["id"]
        assert booking_data["customer_id"] is not None

        # --- Modify ---
        resp = client.patch(
            f"/api/bookings/{booking_id}",
            json={"party_size": 5, "special_requests": "Tavolo vicino alla finestra"},
        )
        assert resp.status_code == 200
        assert resp.json()["party_size"] == 5
        assert resp.json()["special_requests"] == "Tavolo vicino alla finestra"

        # --- Cancel ---
        resp = client.post(f"/api/bookings/{booking_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify 3 events
        db_session.expire_all()
        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking_id)
            .order_by(BookingEvent.created_at)
        ).all()
        assert len(events) == 3
        assert [e.event_type for e in events] == ["created", "modified", "cancelled"]
        assert all("user:owner@trattoriamadonnina.it" == e.changed_by for e in events)


# ===========================================================================
# 2. Repeat customer — booking_count accumulates across bookings
# ===========================================================================


class TestRepeatCustomer:
    def test_three_bookings_same_phone_single_customer(self, client: TestClient, db_session: Session):
        r = _restaurant(db_session)
        phone = "+393405555555"

        for i, d in enumerate([DATE_1, DATE_2, DATE_3]):
            resp = client.post(
                "/api/tools/create-booking",
                headers=TOOL_HEADERS,
                json={
                    "restaurant_id": r.id,
                    "date": d,
                    "time": "20:00:00",
                    "party_size": 2,
                    "customer_name": f"Repeat Customer {i}",
                    "customer_phone": phone,
                    "caller_phone": phone,
                },
            )
            assert resp.status_code == 200

        db_session.expire_all()
        customers = db_session.scalars(
            select(Customer).where(Customer.restaurant_id == r.id)
        ).all()
        # Find the one with booking_count == 3
        matching = [c for c in customers if c.booking_count == 3]
        assert len(matching) == 1
        assert matching[0].last_booking_date is not None


# ===========================================================================
# 3. Capacity — bookings affect capacity correctly
# ===========================================================================


class TestCapacity:
    def test_booking_reduces_remaining_covers(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        # Get capacity before
        resp = client.get("/api/analytics/capacity", params={"restaurant_id": r.id, "date": DATE_1})
        assert resp.status_code == 200
        slots_before = resp.json()["slots"]
        # Find the turno that covers 20:00 (primo: 19:00-21:00).
        primo = next((s for s in slots_before if s["turno"] == "primo"), None)

        # Book a table for 4 in primo turno (time 20:00 falls in primo: 19:00-21:00)
        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": r.id,
                "date": DATE_1,
                "time": "20:00:00",
                "party_size": 4,
                "customer_name": "Capacity Test",
                "customer_phone": "+393401111111",
            },
        )
        assert resp.status_code == 201

        # Get capacity after
        resp = client.get("/api/analytics/capacity", params={"restaurant_id": r.id, "date": DATE_1})
        assert resp.status_code == 200
        slots_after = resp.json()["slots"]
        primo_after = next((s for s in slots_after if s["turno"] == "primo"), None)

        if primo is not None and primo_after is not None:
            assert primo_after["booked_covers"] == primo["booked_covers"] + 4
            assert primo_after["remaining_covers"] == primo["remaining_covers"] - 4


# ===========================================================================
# 4. Settings round-trip — update config and verify validators
# ===========================================================================


class TestSettingsRoundTrip:
    def test_update_turni_and_read_back(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        new_turni = [
            {"name": "pranzo", "start": "12:00", "end": "15:00", "max_covers": 25},
            {"name": "cena", "start": "19:00", "end": "23:00", "max_covers": 45},
        ]
        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={"turni": new_turni},
        )
        assert resp.status_code == 200
        returned = resp.json()
        assert len(returned["turni"]) == 2
        assert returned["turni"][0]["name"] == "pranzo"
        assert returned["turni"][1]["max_covers"] == 45

        # Read back from current endpoint
        resp = client.get("/api/restaurants/current", params={"restaurant_id": r.id})
        assert resp.status_code == 200
        assert resp.json()["turni"][0]["name"] == "pranzo"

    def test_update_opening_hours_validates_format(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        # Invalid format should be rejected
        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={"opening_hours": {"lunch": "noon-3pm"}},
        )
        assert resp.status_code == 422

        # Valid format should work
        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={"opening_hours": {"lunch": "12:00-15:00", "dinner": "19:00-23:30"}},
        )
        assert resp.status_code == 200
        assert resp.json()["opening_hours"]["dinner"] == "19:00-23:30"

    def test_update_booking_rules_validates_constraints(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        # min > max should be rejected
        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={"booking_rules": {"min_party": 10, "max_party": 5}},
        )
        assert resp.status_code == 422

        # Valid rules should be accepted
        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={
                "booking_rules": {
                    "min_party": 1,
                    "max_party": 15,
                    "large_group_threshold": 8,
                    "max_advance_days": 90,
                    "min_lead_hours": 3,
                }
            },
        )
        assert resp.status_code == 200
        assert resp.json()["booking_rules"]["max_party"] == 15

    def test_update_weekly_closures_normalizes(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={"weekly_closures": ["Tuesday", "WEDNESDAY"]},
        )
        assert resp.status_code == 200
        assert resp.json()["weekly_closures"] == ["tuesday", "wednesday"]

    def test_update_assistant_settings(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={
                "assistant_settings": {
                    "llm_provider": "openai",
                    "openai_model": "gpt-5",
                    "reasoning_effort": "medium",
                    "response_verbosity": "high",
                    "custom_greeting": "Buonasera, benvenuti!",
                    "agent_style_notes": "Formal, use Lei.",
                },
            },
        )
        assert resp.status_code == 200
        settings = resp.json()["assistant_settings"]
        assert settings["openai_model"] == "gpt-5"
        assert settings["reasoning_effort"] == "medium"
        assert settings["custom_greeting"] == "Buonasera, benvenuti!"

    def test_sending_extra_fields_ignored(self, client: TestClient, db_session: Session):
        """The dashboard sends the entire restaurant object including id,
        created_at, updated_at. These should be silently ignored."""
        login(client)
        r = _restaurant(db_session)

        resp = client.patch(
            f"/api/restaurants/{r.id}?sync_agent=false",
            json={
                "id": "should-be-ignored",
                "created_at": "1999-01-01T00:00:00",
                "updated_at": "1999-01-01T00:00:00",
                "name": "Updated Name",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        # id should NOT have changed
        assert resp.json()["id"] == r.id


# ===========================================================================
# 5. Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_double_cancel_is_safe(self, client: TestClient, db_session: Session):
        r = _restaurant(db_session)
        resp = client.post(
            "/api/tools/create-booking",
            headers=TOOL_HEADERS,
            json={
                "restaurant_id": r.id,
                "date": DATE_1,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Double Cancel",
                "customer_phone": "+393407777777",
                "caller_phone": "+393407777777",
            },
        )
        code = resp.json()["confirmation_code"]

        # Cancel once
        resp = client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code},
        )
        assert resp.status_code == 200

        # Cancel again — should not crash. Returns 404 because
        # the tool endpoint only finds confirmed/modified bookings
        resp = client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code},
        )
        assert resp.status_code == 404

    def test_modify_nonexistent_booking_returns_error(self, client: TestClient):
        resp = client.post(
            "/api/tools/modify-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": "NONEXISTENT", "changes": {"party_size": 4}},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json()["success"] is False

    def test_booking_on_closure_day_rejected(self, client: TestClient, db_session: Session):
        """Booking on Monday (the seeded closure day) should be rejected."""
        r = _restaurant(db_session)
        # Find the next Monday
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = (today + timedelta(days=days_until_monday)).isoformat()

        resp = client.post(
            "/api/tools/create-booking",
            headers=TOOL_HEADERS,
            json={
                "restaurant_id": r.id,
                "date": next_monday,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Monday Test",
                "customer_phone": "+393408888888",
                "caller_phone": "+393408888888",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_booking_list_filters_by_date(self, client: TestClient, db_session: Session):
        login(client)
        r = _restaurant(db_session)

        # Create bookings on different dates
        for d in [DATE_1, DATE_2]:
            client.post(
                "/api/bookings",
                json={
                    "restaurant_id": r.id,
                    "date": d,
                    "time": "20:00:00",
                    "party_size": 2,
                    "customer_name": f"Filter Test {d}",
                    "customer_phone": f"+3934099{d.replace('-', '')[-5:]}",
                },
            )

        # Filter by date_from=DATE_2
        resp = client.get("/api/bookings", params={"date_from": DATE_2})
        assert resp.status_code == 200
        bookings = resp.json()
        # All returned bookings should be on DATE_2 or later
        for b in bookings:
            assert b["date"] >= DATE_2

    def test_cancel_modified_booking_logs_correct_previous_status(
        self, client: TestClient, db_session: Session
    ):
        """Cancelling a 'modified' booking should log from='modified', not 'confirmed'."""
        r = _restaurant(db_session)
        result = client.post(
            "/api/tools/create-booking",
            headers=TOOL_HEADERS,
            json={
                "restaurant_id": r.id,
                "date": DATE_1,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Status Track",
                "customer_phone": "+393406666666",
                "caller_phone": "+393406666666",
            },
        )
        code = result.json()["confirmation_code"]

        # Modify to set status to "modified"
        client.post(
            "/api/tools/modify-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code, "changes": {"party_size": 5}},
        )

        # Cancel it
        client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": code},
        )

        db_session.expire_all()
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == code)
        )
        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        cancel_event = [e for e in events if e.event_type == "cancelled"][0]
        assert cancel_event.changes["status"]["from"] == "modified"
        assert cancel_event.changes["status"]["to"] == "cancelled"

    def test_special_requests_only_update_keeps_confirmed_status(
        self, client: TestClient, db_session: Session
    ):
        """Updating only special_requests should NOT change status to 'modified'."""
        login(client)
        r = _restaurant(db_session)

        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": r.id,
                "date": DATE_2,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "SR Only",
                "customer_phone": "+393405551234",
            },
        )
        assert resp.status_code == 201
        booking_id = resp.json()["id"]
        assert resp.json()["status"] == "confirmed"

        resp = client.patch(
            f"/api/bookings/{booking_id}",
            json={"special_requests": "Allergia noci"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"
        assert resp.json()["special_requests"] == "Allergia noci"
