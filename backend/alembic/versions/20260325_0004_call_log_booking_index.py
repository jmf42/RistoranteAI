"""Add missing index on call_logs.booking_id.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_call_logs_booking_id", "call_logs", ["booking_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_call_logs_booking_id", table_name="call_logs")
