"""Persist OpenAI Realtime prompt and session config per restaurant.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("openai_prompt_override", sa.Text(), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column(
            "openai_realtime_settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurants", "openai_realtime_settings")
    op.drop_column("restaurants", "openai_prompt_override")
