from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("twilio_phone", sa.String(length=30), nullable=True),
        sa.Column("elevenlabs_agent_id", sa.String(length=120), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("opening_hours", sa.JSON(), nullable=False),
        sa.Column("weekly_closures", sa.JSON(), nullable=False),
        sa.Column("closure_dates", sa.JSON(), nullable=False),
        sa.Column("turni", sa.JSON(), nullable=False),
        sa.Column("booking_rules", sa.JSON(), nullable=False),
        sa.Column("assistant_settings", sa.JSON(), nullable=False),
        sa.Column("escalation_phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restaurants_slug"), "restaurants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("confirmation_code", sa.String(length=20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("turno", sa.String(length=40), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("customer_name_encrypted", sa.Text(), nullable=False),
        sa.Column("customer_phone_encrypted", sa.Text(), nullable=False),
        sa.Column("customer_phone_hash", sa.String(length=64), nullable=False),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_confirmation_code"), "bookings", ["confirmation_code"], unique=True)
    op.create_index(op.f("ix_bookings_customer_phone_hash"), "bookings", ["customer_phone_hash"], unique=False)
    op.create_index(op.f("ix_bookings_date"), "bookings", ["date"], unique=False)
    op.create_index(op.f("ix_bookings_restaurant_id"), "bookings", ["restaurant_id"], unique=False)
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"], unique=False)
    op.create_index(op.f("ix_bookings_turno"), "bookings", ["turno"], unique=False)

    op.create_table(
        "call_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=False),
        sa.Column("elevenlabs_conversation_id", sa.String(length=120), nullable=True),
        sa.Column("caller_phone_hash", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("booking_id", sa.String(length=36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("transcript_preview", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_call_logs_caller_phone_hash"), "call_logs", ["caller_phone_hash"], unique=False
    )
    op.create_index(
        op.f("ix_call_logs_elevenlabs_conversation_id"),
        "call_logs",
        ["elevenlabs_conversation_id"],
        unique=True,
    )
    op.create_index(op.f("ix_call_logs_outcome"), "call_logs", ["outcome"], unique=False)
    op.create_index(op.f("ix_call_logs_restaurant_id"), "call_logs", ["restaurant_id"], unique=False)
    op.create_index(op.f("ix_call_logs_started_at"), "call_logs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_call_logs_started_at"), table_name="call_logs")
    op.drop_index(op.f("ix_call_logs_restaurant_id"), table_name="call_logs")
    op.drop_index(op.f("ix_call_logs_outcome"), table_name="call_logs")
    op.drop_index(op.f("ix_call_logs_elevenlabs_conversation_id"), table_name="call_logs")
    op.drop_index(op.f("ix_call_logs_caller_phone_hash"), table_name="call_logs")
    op.drop_table("call_logs")

    op.drop_index(op.f("ix_bookings_turno"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_status"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_restaurant_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_date"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_customer_phone_hash"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_confirmation_code"), table_name="bookings")
    op.drop_table("bookings")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_restaurants_slug"), table_name="restaurants")
    op.drop_table("restaurants")
