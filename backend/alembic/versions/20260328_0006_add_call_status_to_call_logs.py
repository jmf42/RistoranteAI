"""Add call_status column to call_logs.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "call_logs",
        sa.Column("call_status", sa.String(20), server_default="unknown", nullable=False),
    )
    op.create_index(op.f("ix_call_logs_call_status"), "call_logs", ["call_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_call_logs_call_status"), table_name="call_logs")
    op.drop_column("call_logs", "call_status")
