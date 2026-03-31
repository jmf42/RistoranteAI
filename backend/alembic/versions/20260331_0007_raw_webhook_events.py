"""Add raw webhook events inbox table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_webhook_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=120), nullable=False),
        sa.Column("restaurant_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "event_key", name="uq_raw_webhook_events_source_event_key"),
    )
    op.create_index(op.f("ix_raw_webhook_events_source"), "raw_webhook_events", ["source"])
    op.create_index(op.f("ix_raw_webhook_events_restaurant_id"), "raw_webhook_events", ["restaurant_id"])
    op.create_index(op.f("ix_raw_webhook_events_status"), "raw_webhook_events", ["status"])
    op.create_index(op.f("ix_raw_webhook_events_received_at"), "raw_webhook_events", ["received_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_webhook_events_received_at"), table_name="raw_webhook_events")
    op.drop_index(op.f("ix_raw_webhook_events_status"), table_name="raw_webhook_events")
    op.drop_index(op.f("ix_raw_webhook_events_restaurant_id"), table_name="raw_webhook_events")
    op.drop_index(op.f("ix_raw_webhook_events_source"), table_name="raw_webhook_events")
    op.drop_table("raw_webhook_events")
