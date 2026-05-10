"""Add public online reservation support.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "online_booking_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    op.add_column("bookings", sa.Column("customer_email_encrypted", sa.Text(), nullable=True))
    op.add_column("bookings", sa.Column("customer_email_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("channel_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "bookings",
        sa.Column("guest_access_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("bookings", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.create_index("ix_bookings_customer_email_hash", "bookings", ["customer_email_hash"], unique=False)
    op.create_index(
        "uq_bookings_restaurant_source_idempotency_key",
        "bookings",
        ["restaurant_id", "source", "idempotency_key"],
        unique=True,
    )

    op.add_column("customers", sa.Column("email_encrypted", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("email_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_customers_email_hash", "customers", ["email_hash"], unique=False)

    op.create_table(
        "booking_guest_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("booking_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False, server_default="manage"),
        sa.Column("access_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_booking_guest_tokens_booking_id", "booking_guest_tokens", ["booking_id"], unique=False)
    op.create_index("ix_booking_guest_tokens_purpose", "booking_guest_tokens", ["purpose"], unique=False)
    op.create_index("ix_booking_guest_tokens_expires_at", "booking_guest_tokens", ["expires_at"], unique=False)

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("booking_id", sa.String(length=36), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="email"),
        sa.Column("template_key", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="smtp"),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_outbox_restaurant_id", "notification_outbox", ["restaurant_id"], unique=False)
    op.create_index("ix_notification_outbox_booking_id", "notification_outbox", ["booking_id"], unique=False)
    op.create_index("ix_notification_outbox_channel", "notification_outbox", ["channel"], unique=False)
    op.create_index("ix_notification_outbox_template_key", "notification_outbox", ["template_key"], unique=False)
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"], unique=False)
    op.create_index("ix_notification_outbox_available_at", "notification_outbox", ["available_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_available_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_template_key", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_channel", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_booking_id", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_restaurant_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")

    op.drop_index("ix_booking_guest_tokens_expires_at", table_name="booking_guest_tokens")
    op.drop_index("ix_booking_guest_tokens_purpose", table_name="booking_guest_tokens")
    op.drop_index("ix_booking_guest_tokens_booking_id", table_name="booking_guest_tokens")
    op.drop_table("booking_guest_tokens")

    op.drop_index("ix_customers_email_hash", table_name="customers")
    op.drop_column("customers", "email_hash")
    op.drop_column("customers", "email_encrypted")

    op.drop_index("uq_bookings_restaurant_source_idempotency_key", table_name="bookings")
    op.drop_index("ix_bookings_customer_email_hash", table_name="bookings")
    op.drop_column("bookings", "idempotency_key")
    op.drop_column("bookings", "guest_access_version")
    op.drop_column("bookings", "channel_metadata")
    op.drop_column("bookings", "customer_email_hash")
    op.drop_column("bookings", "customer_email_encrypted")

    op.drop_column("restaurants", "online_booking_settings")
