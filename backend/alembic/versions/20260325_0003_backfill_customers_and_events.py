"""Backfill customers, booking customer links, and baseline booking events.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-25
"""

from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    bookings_table = sa.table(
        "bookings",
        sa.column("id", sa.String(36)),
        sa.column("restaurant_id", sa.String(36)),
        sa.column("confirmation_code", sa.String(20)),
        sa.column("date", sa.Date()),
        sa.column("time", sa.Time()),
        sa.column("party_size", sa.Integer()),
        sa.column("customer_name_encrypted", sa.Text()),
        sa.column("customer_phone_encrypted", sa.Text()),
        sa.column("customer_phone_hash", sa.String(64)),
        sa.column("status", sa.String(20)),
        sa.column("source", sa.String(20)),
        sa.column("customer_id", sa.String(36)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    customers_table = sa.table(
        "customers",
        sa.column("id", sa.String(36)),
        sa.column("restaurant_id", sa.String(36)),
        sa.column("phone_hash", sa.String(64)),
        sa.column("name_encrypted", sa.Text()),
        sa.column("phone_encrypted", sa.Text()),
        sa.column("booking_count", sa.Integer()),
        sa.column("no_show_count", sa.Integer()),
        sa.column("cancellation_count", sa.Integer()),
        sa.column("last_booking_date", sa.Date()),
        sa.column("notes", sa.Text()),
    )
    booking_events_table = sa.table(
        "booking_events",
        sa.column("id", sa.String(36)),
        sa.column("booking_id", sa.String(36)),
        sa.column("event_type", sa.String(30)),
        sa.column("changed_by", sa.String(40)),
        sa.column("changes", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    bookings = connection.execute(
        sa.select(
            bookings_table.c.id,
            bookings_table.c.restaurant_id,
            bookings_table.c.confirmation_code,
            bookings_table.c.date,
            bookings_table.c.time,
            bookings_table.c.party_size,
            bookings_table.c.customer_name_encrypted,
            bookings_table.c.customer_phone_encrypted,
            bookings_table.c.customer_phone_hash,
            bookings_table.c.status,
            bookings_table.c.source,
            bookings_table.c.customer_id,
            bookings_table.c.created_at,
        ).order_by(
            bookings_table.c.restaurant_id,
            bookings_table.c.customer_phone_hash,
            bookings_table.c.date,
            bookings_table.c.created_at,
        )
    ).mappings().all()

    existing_customers = {
        (row.restaurant_id, row.phone_hash): row.id
        for row in connection.execute(
            sa.select(
                customers_table.c.id,
                customers_table.c.restaurant_id,
                customers_table.c.phone_hash,
            )
        ).mappings()
    }
    existing_event_booking_ids = set(
        connection.execute(sa.select(booking_events_table.c.booking_id)).scalars().all()
    )

    grouped_bookings: dict[tuple[str, str], list[sa.RowMapping]] = defaultdict(list)
    for booking in bookings:
        if booking.customer_phone_hash:
            grouped_bookings[(booking.restaurant_id, booking.customer_phone_hash)].append(booking)

    customer_inserts: list[dict[str, object]] = []
    booking_updates: list[dict[str, str]] = []
    for key, customer_bookings in grouped_bookings.items():
        customer_id = existing_customers.get(key)
        if customer_id is None:
            latest_booking = max(customer_bookings, key=lambda booking: (booking.date, booking.created_at))
            customer_id = str(uuid4())
            existing_customers[key] = customer_id
            customer_inserts.append(
                {
                    "id": customer_id,
                    "restaurant_id": latest_booking.restaurant_id,
                    "phone_hash": latest_booking.customer_phone_hash,
                    "name_encrypted": latest_booking.customer_name_encrypted,
                    "phone_encrypted": latest_booking.customer_phone_encrypted,
                    "booking_count": len(customer_bookings),
                    "no_show_count": sum(1 for booking in customer_bookings if booking.status == "no_show"),
                    "cancellation_count": sum(1 for booking in customer_bookings if booking.status == "cancelled"),
                    "last_booking_date": max(booking.date for booking in customer_bookings),
                    "notes": None,
                }
            )

        for booking in customer_bookings:
            if booking.customer_id != customer_id:
                booking_updates.append({"booking_id": booking.id, "customer_id": customer_id})

    if customer_inserts:
        connection.execute(customers_table.insert(), customer_inserts)

    for update in booking_updates:
        connection.execute(
            sa.update(bookings_table)
            .where(bookings_table.c.id == update["booking_id"])
            .values(customer_id=update["customer_id"])
        )

    event_inserts: list[dict[str, object]] = []
    for booking in bookings:
        if booking.id in existing_event_booking_ids:
            continue
        changed_by = "ai_phone" if booking.source == "ai_phone" else "user:migration"
        event_inserts.append(
            {
                "id": str(uuid4()),
                "booking_id": booking.id,
                "event_type": "created",
                "changed_by": changed_by,
                "changes": {
                    "confirmation_code": booking.confirmation_code,
                    "date": str(booking.date),
                    "time": str(booking.time),
                    "party_size": booking.party_size,
                    "status": booking.status,
                    "source": booking.source,
                },
                "created_at": booking.created_at,
            }
        )

    if event_inserts:
        connection.execute(booking_events_table.insert(), event_inserts)


def downgrade() -> None:
    # This migration performs data backfill only. Reversing it safely would require
    # distinguishing backfilled rows from legitimate live data, which is not reliable.
    pass
