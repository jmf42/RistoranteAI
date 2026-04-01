"""Tests for: customer entity, booking events audit trail, restaurant validators,
multi-restaurant access via user_restaurants."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Booking, BookingEvent, Customer, Restaurant, User, UserRestaurant
from app.schemas.restaurant import RestaurantCreate, RestaurantUpdate
from tests.conftest import login

CLOSED_WEEKDAY = "monday"


def _next_open_date(offset: int = 0) -> str:
    """Return the Nth future open date (not Monday, the seeded restaurant's closure day)."""
    candidate = date.today() + timedelta(days=5)
    skipped = 0
    while True:
        if candidate.strftime("%A").lower() != CLOSED_WEEKDAY:
            if skipped == offset:
                return candidate.isoformat()
            skipped += 1
        candidate += timedelta(days=1)

TOOL_HEADERS = {"X-Ristorante-Tool-Secret": "local-tool-secret"}
FUTURE_DATE = _next_open_date(0)
FUTURE_DATE_2 = _next_open_date(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_restaurant(db: Session) -> Restaurant:
    return db.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-da-mario"))


def create_tool_booking(
    client: TestClient,
    restaurant_id: str,
    phone: str,
    name: str = "Test",
    date_str: str = FUTURE_DATE,
) -> dict:
    resp = client.post(
        "/api/tools/create-booking",
        headers=TOOL_HEADERS,
        json={
            "restaurant_id": restaurant_id,
            "date": date_str,
            "time": "20:00:00",
            "party_size": 2,
            "customer_name": name,
            "customer_phone": phone,
            "caller_phone": phone,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    return resp.json()


# ===========================================================================
# B. Restaurant config validators
# ===========================================================================


class TestRestaurantValidators:
    def test_valid_turni_accepted(self):
        r = RestaurantCreate(
            slug="test", name="Test", address="Via Test 1",
            turni=[{"name": "primo", "start": "19:00", "end": "21:00", "max_covers": 40}],
        )
        assert r.turni[0]["name"] == "primo"

    def test_turni_missing_key_rejected(self):
        with pytest.raises(Exception, match="missing required keys"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                turni=[{"name": "primo", "start": "19:00", "end": "21:00"}],  # no max_covers
            )

    def test_turni_bad_start_time_rejected(self):
        with pytest.raises(Exception, match="start.*HH:MM"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                turni=[{"name": "primo", "start": "7pm", "end": "21:00", "max_covers": 40}],
            )

    def test_turni_zero_covers_rejected(self):
        with pytest.raises(Exception, match="max_covers.*positive"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                turni=[{"name": "primo", "start": "19:00", "end": "21:00", "max_covers": 0}],
            )

    def test_weekly_closures_normalized_to_lowercase(self):
        r = RestaurantCreate(
            slug="test", name="Test", address="Via Test 1",
            weekly_closures=["Monday", "SUNDAY"],
        )
        assert r.weekly_closures == ["monday", "sunday"]

    def test_weekly_closures_invalid_day_rejected(self):
        with pytest.raises(Exception, match="Invalid closure day"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                weekly_closures=["lunedi"],
            )

    def test_opening_hours_bad_format_rejected(self):
        with pytest.raises(Exception, match="Expected format HH:MM-HH:MM"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                opening_hours={"dinner": "7pm-11pm"},
            )

    def test_opening_hours_valid_format_accepted(self):
        r = RestaurantCreate(
            slug="test", name="Test", address="Via Test 1",
            opening_hours={"lunch": "12:00-15:00", "dinner": "19:00-23:30"},
        )
        assert "dinner" in r.opening_hours

    def test_booking_rules_min_greater_than_max_rejected(self):
        with pytest.raises(Exception, match="min_party cannot be greater than max_party"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                booking_rules={"min_party": 10, "max_party": 5},
            )

    def test_booking_rules_negative_value_rejected(self):
        with pytest.raises(Exception, match="non-negative integer"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                booking_rules={"min_party": -1},
            )

    def test_closure_dates_bad_format_rejected(self):
        with pytest.raises(Exception, match="YYYY-MM-DD"):
            RestaurantCreate(
                slug="test", name="Test", address="Via Test 1",
                closure_dates=["25-12-2026"],
            )

    def test_closure_dates_valid_format_accepted(self):
        r = RestaurantCreate(
            slug="test", name="Test", address="Via Test 1",
            closure_dates=["2026-12-25", "2027-01-01"],
        )
        assert len(r.closure_dates) == 2

    def test_update_with_none_fields_passes_through(self):
        u = RestaurantUpdate(turni=None, weekly_closures=None, opening_hours=None)
        assert u.turni is None
        assert u.weekly_closures is None

    def test_api_rejects_bad_turni_on_create(self, client: TestClient):
        login(client, email="operator@ristorante.ai")
        resp = client.post(
            "/api/restaurants",
            json={
                "slug": "bad-config",
                "name": "Bad Config",
                "address": "Via Test 1",
                "turni": [{"name": "primo", "start": "bad-time", "end": "21:00", "max_covers": 20}],
                "booking_rules": {"min_party": 1, "max_party": 10},
            },
        )
        assert resp.status_code == 422

    def test_api_rejects_bad_weekly_closures_on_update(self, client: TestClient, db_session: Session):
        login(client)
        restaurant = get_restaurant(db_session)
        resp = client.patch(
            f"/api/restaurants/{restaurant.id}",
            json={"weekly_closures": ["lunedi", "martedi"]},
        )
        assert resp.status_code == 422


# ===========================================================================
# C. Booking events audit trail
# ===========================================================================


class TestBookingAuditTrail:
    def test_create_booking_logs_created_event(self, client: TestClient, db_session: Session):
        login(client)
        restaurant = get_restaurant(db_session)
        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": restaurant.id,
                "date": FUTURE_DATE,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Audit Test",
                "customer_phone": "+393331110001",
            },
        )
        assert resp.status_code == 201
        booking_id = resp.json()["id"]

        events = db_session.scalars(
            select(BookingEvent).where(BookingEvent.booking_id == booking_id)
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert "confirmation_code" in events[0].changes
        assert "date" in events[0].changes
        assert "party_size" in events[0].changes

    def test_create_event_records_changed_by_user(self, client: TestClient, db_session: Session):
        login(client)
        restaurant = get_restaurant(db_session)
        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": restaurant.id,
                "date": FUTURE_DATE,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Audit User",
                "customer_phone": "+393331110002",
            },
        )
        assert resp.status_code == 201
        booking_id = resp.json()["id"]

        event = db_session.scalar(
            select(BookingEvent).where(BookingEvent.booking_id == booking_id)
        )
        assert event.changed_by == "user:owner@trattoriamadonnina.it"

    def test_ai_tool_create_logs_ai_phone_changed_by(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        result = create_tool_booking(client, restaurant.id, "+393331110003")
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == result["confirmation_code"])
        )
        event = db_session.scalar(
            select(BookingEvent).where(BookingEvent.booking_id == booking.id)
        )
        assert event.changed_by == "ai_phone"
        assert event.event_type == "created"

    def test_update_booking_logs_modified_event_with_changes(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        result = create_tool_booking(client, restaurant.id, "+393331110004")
        confirmation_code = result["confirmation_code"]
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == confirmation_code)
        )

        resp = client.post(
            "/api/tools/modify-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": confirmation_code, "changes": {"party_size": 4}},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        db_session.expire_all()
        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        assert len(events) == 2
        modified = events[1]
        assert modified.event_type == "modified"
        assert modified.changes["party_size"]["from"] == 2
        assert modified.changes["party_size"]["to"] == 4

    def test_cancel_booking_logs_cancelled_event(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        result = create_tool_booking(client, restaurant.id, "+393331110005")
        confirmation_code = result["confirmation_code"]
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == confirmation_code)
        )

        resp = client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": confirmation_code},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        events = db_session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        assert any(e.event_type == "cancelled" for e in events)

    def test_no_event_logged_when_booking_fails(self, client: TestClient, db_session: Session):
        resp = client.post(
            "/api/tools/create-booking",
            headers=TOOL_HEADERS,
            json={
                "restaurant_id": "nonexistent-id",
                "date": FUTURE_DATE,
                "time": "20:00:00",
                "party_size": 2,
                "customer_name": "Ghost",
                "customer_phone": "+393331119999",
            },
        )
        assert resp.status_code == 404
        # Only events from seeded bookings (which are 3 — created events)
        events = db_session.scalars(select(BookingEvent)).all()
        for e in events:
            assert e.event_type == "created"  # no cancelled/modified from failed attempt


# ===========================================================================
# D. Customer entity — upsert and stats
# ===========================================================================


class TestCustomerEntity:
    def test_booking_creates_customer_record(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        create_tool_booking(client, restaurant.id, "+393330010001", name="Mario Rossi")

        customer = db_session.scalar(
            select(Customer).where(Customer.restaurant_id == restaurant.id)
            .order_by(Customer.created_at.desc())
        )
        assert customer is not None
        assert customer.booking_count == 1
        assert customer.last_booking_date is not None

    def test_second_booking_same_phone_upserts_customer(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        phone = "+393330010002"
        create_tool_booking(client, restaurant.id, phone, date_str=FUTURE_DATE)
        create_tool_booking(client, restaurant.id, phone, date_str=FUTURE_DATE_2)

        customers = db_session.scalars(
            select(Customer).where(
                Customer.restaurant_id == restaurant.id,
                Customer.phone_hash.is_not(None),
            )
        ).all()
        matching = [c for c in customers if c.booking_count == 2]
        assert len(matching) == 1, "should upsert, not create two records"
        assert matching[0].booking_count == 2

    def test_different_phones_create_separate_customers(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        before = db_session.scalars(select(Customer).where(Customer.restaurant_id == restaurant.id)).all()
        before_count = len(before)

        create_tool_booking(client, restaurant.id, "+393330010010")
        create_tool_booking(client, restaurant.id, "+393330010011")

        after = db_session.scalars(select(Customer).where(Customer.restaurant_id == restaurant.id)).all()
        assert len(after) == before_count + 2

    def test_booking_has_customer_id_set(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        result = create_tool_booking(client, restaurant.id, "+393330010020")
        booking = db_session.scalar(
            select(Booking).where(Booking.confirmation_code == result["confirmation_code"])
        )
        assert booking.customer_id is not None

    def test_api_response_includes_customer_id(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        result = create_tool_booking(client, restaurant.id, "+393330010021")

        login(client)
        bookings_resp = client.get("/api/bookings", params={"date_from": FUTURE_DATE})
        assert bookings_resp.status_code == 200
        matching = [b for b in bookings_resp.json() if b["confirmation_code"] == result["confirmation_code"]]
        assert len(matching) == 1
        assert matching[0]["customer_id"] is not None

    def test_cancellation_increments_customer_cancellation_count(self, client: TestClient, db_session: Session):
        restaurant = get_restaurant(db_session)
        phone = "+393330010030"
        result = create_tool_booking(client, restaurant.id, phone)

        customer_before = db_session.scalar(
            select(Customer).where(
                Customer.restaurant_id == restaurant.id,
                Customer.booking_count >= 1,
            ).order_by(Customer.created_at.desc())
        )
        cancellations_before = customer_before.cancellation_count

        client.post(
            "/api/tools/cancel-booking",
            headers=TOOL_HEADERS,
            json={"confirmation_code": result["confirmation_code"]},
        )
        db_session.expire_all()

        customer_after = db_session.get(Customer, customer_before.id)
        assert customer_after.cancellation_count == cancellations_before + 1

    def test_dashboard_booking_also_creates_customer(self, client: TestClient, db_session: Session):
        login(client)
        restaurant = get_restaurant(db_session)
        phone = "+393330010040"

        resp = client.post(
            "/api/bookings",
            json={
                "restaurant_id": restaurant.id,
                "date": FUTURE_DATE,
                "time": "20:00:00",
                "party_size": 3,
                "customer_name": "Dashboard Customer",
                "customer_phone": phone,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["customer_id"] is not None

        customer = db_session.scalar(
            select(Customer).where(Customer.restaurant_id == restaurant.id)
            .order_by(Customer.created_at.desc())
        )
        assert customer is not None
        assert customer.booking_count >= 1


# ===========================================================================
# G. Multi-restaurant access (user_restaurants)
# ===========================================================================


class TestMultiRestaurantAccess:
    def test_auth_me_returns_restaurant_ids_list(self, client: TestClient):
        login(client)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert "restaurant_ids" in user
        assert isinstance(user["restaurant_ids"], list)
        assert len(user["restaurant_ids"]) >= 1

    def test_owner_can_access_linked_restaurant_via_user_restaurants(
        self, client: TestClient, db_session: Session
    ):
        # Create a second restaurant
        second = Restaurant(
            slug="ristorante-secondo",
            name="Ristorante Secondo",
            address="Via Po 10",
            turni=[{"name": "serale", "start": "19:00", "end": "22:00", "max_covers": 30}],
            booking_rules={
                "min_party": 1,
                "max_party": 10,
                "large_group_threshold": 6,
                "max_advance_days": 30,
                "min_lead_hours": 2,
            },
        )
        db_session.add(second)
        db_session.flush()

        owner = db_session.scalar(select(User).where(User.email == "owner@trattoriamadonnina.it"))
        link = UserRestaurant(user_id=owner.id, restaurant_id=second.id, role="owner")
        db_session.add(link)
        db_session.commit()

        login(client)
        # Owner can fetch bookings for the second restaurant
        resp = client.get("/api/bookings", params={"restaurant_id": second.id})
        assert resp.status_code == 200  # not 403

    def test_owner_cannot_access_unlinked_restaurant(self, client: TestClient, db_session: Session):
        unlinked = Restaurant(
            slug="ristorante-unlinked",
            name="Unlinked Restaurant",
            address="Via Nessuno 1",
            turni=[{"name": "serale", "start": "19:00", "end": "22:00", "max_covers": 20}],
            booking_rules={
                "min_party": 1,
                "max_party": 10,
                "large_group_threshold": 6,
                "max_advance_days": 30,
                "min_lead_hours": 2,
            },
        )
        db_session.add(unlinked)
        db_session.commit()

        login(client)
        resp = client.get("/api/bookings", params={"restaurant_id": unlinked.id})
        assert resp.status_code == 403

    def test_login_response_includes_restaurant_ids(self, client: TestClient):
        resp = client.post(
            "/api/auth/login",
            json={"email": "owner@trattoriamadonnina.it", "password": "madonnina"},
        )
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert "restaurant_ids" in user
        assert user["restaurant_id"] in user["restaurant_ids"]

    def test_operator_can_access_any_restaurant(self, client: TestClient, db_session: Session):
        second = Restaurant(
            slug="any-restaurant",
            name="Any Restaurant",
            address="Via Qualsiasi 1",
            turni=[{"name": "serale", "start": "19:00", "end": "22:00", "max_covers": 20}],
            booking_rules={
                "min_party": 1,
                "max_party": 10,
                "large_group_threshold": 6,
                "max_advance_days": 30,
                "min_lead_hours": 2,
            },
        )
        db_session.add(second)
        db_session.commit()

        login(client, email="operator@ristorante.ai")
        resp = client.get("/api/bookings", params={"restaurant_id": second.id})
        assert resp.status_code == 200

    def test_user_restaurants_unique_constraint(self, client: TestClient, db_session: Session):
        owner = db_session.scalar(select(User).where(User.email == "owner@trattoriamadonnina.it"))
        restaurant = get_restaurant(db_session)

        link1 = UserRestaurant(user_id=owner.id, restaurant_id=restaurant.id, role="owner")
        db_session.add(link1)
        db_session.flush()

        link2 = UserRestaurant(user_id=owner.id, restaurant_id=restaurant.id, role="owner")
        db_session.add(link2)
        with pytest.raises(IntegrityError):
            db_session.flush()
