from __future__ import annotations

from app.models import Booking


def test_booking_declares_composite_indexes_for_live_call_queries():
    index_names = {index.name for index in Booking.__table__.indexes}

    assert "ix_bookings_restaurant_date_status_turno" in index_names
    assert "ix_bookings_restaurant_date_time_party_phone_status_created" in index_names
