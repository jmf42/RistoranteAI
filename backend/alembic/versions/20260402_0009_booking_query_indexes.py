"""Add composite indexes for booking availability and duplicate lookups.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-02
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_bookings_restaurant_date_status_turno",
        "bookings",
        ["restaurant_id", "date", "status", "turno"],
        unique=False,
    )
    op.create_index(
        "ix_bookings_restaurant_date_time_party_phone_status_created",
        "bookings",
        [
            "restaurant_id",
            "date",
            "time",
            "party_size",
            "customer_phone_hash",
            "status",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_restaurant_date_time_party_phone_status_created", table_name="bookings")
    op.drop_index("ix_bookings_restaurant_date_status_turno", table_name="bookings")
