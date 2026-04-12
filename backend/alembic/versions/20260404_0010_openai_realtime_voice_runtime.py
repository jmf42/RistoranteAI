"""Add provider-agnostic voice runtime columns for OpenAI Realtime.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("voice_provider", sa.String(length=40), nullable=False, server_default="openai_realtime"),
    )

    op.add_column(
        "call_logs",
        sa.Column("voice_provider", sa.String(length=40), nullable=False, server_default="openai_realtime"),
    )
    op.add_column(
        "call_logs",
        sa.Column("provider_call_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "call_logs",
        sa.Column("twilio_call_sid", sa.String(length=120), nullable=True),
    )

    op.create_index("ix_call_logs_provider_call_id", "call_logs", ["provider_call_id"], unique=False)
    op.create_index("ix_call_logs_twilio_call_sid", "call_logs", ["twilio_call_sid"], unique=False)
    op.create_index("ix_call_logs_voice_provider", "call_logs", ["voice_provider"], unique=False)

    op.execute(
        """
        UPDATE call_logs
        SET provider_call_id = COALESCE(provider_call_id, elevenlabs_conversation_id),
            voice_provider = CASE
                WHEN elevenlabs_conversation_id IS NOT NULL THEN 'elevenlabs'
                ELSE 'openai_realtime'
            END
        """
    )
    op.execute(
        """
        UPDATE restaurants
        SET voice_provider = 'openai_realtime'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_call_logs_voice_provider", table_name="call_logs")
    op.drop_index("ix_call_logs_twilio_call_sid", table_name="call_logs")
    op.drop_index("ix_call_logs_provider_call_id", table_name="call_logs")
    op.drop_column("call_logs", "twilio_call_sid")
    op.drop_column("call_logs", "provider_call_id")
    op.drop_column("call_logs", "voice_provider")
    op.drop_column("restaurants", "voice_provider")
