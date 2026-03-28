"""Flatten assistant_settings JSON into top-level columns; add token_valid_after to users.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Users: add token_valid_after for JWT revocation ---
    op.add_column("users", sa.Column("token_valid_after", sa.DateTime(timezone=True), nullable=True))

    # --- Restaurants: flatten assistant_settings ---
    op.add_column("restaurants", sa.Column("custom_greeting", sa.Text(), nullable=True))
    op.add_column(
        "restaurants",
        sa.Column(
            "agent_style_notes",
            sa.Text(),
            nullable=True,
            server_default="Warm, concise, premium Italian hospitality tone.",
        ),
    )

    # Migrate data from JSON column to new columns (PostgreSQL)
    # For SQLite (tests), the JSON extraction syntax differs
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE restaurants SET "
            "custom_greeting = assistant_settings->>'custom_greeting', "
            "agent_style_notes = COALESCE(assistant_settings->>'agent_style_notes', "
            "'Warm, concise, premium Italian hospitality tone.') "
            "WHERE assistant_settings IS NOT NULL"
        )
    else:
        # SQLite uses json_extract
        op.execute(
            "UPDATE restaurants SET "
            "custom_greeting = json_extract(assistant_settings, '$.custom_greeting'), "
            "agent_style_notes = COALESCE(json_extract(assistant_settings, '$.agent_style_notes'), "
            "'Warm, concise, premium Italian hospitality tone.') "
            "WHERE assistant_settings IS NOT NULL"
        )

    op.drop_column("restaurants", "assistant_settings")


def downgrade() -> None:
    # Recreate assistant_settings JSON column
    op.add_column("restaurants", sa.Column("assistant_settings", sa.JSON(), nullable=False, server_default="{}"))

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE restaurants SET assistant_settings = "
            "json_build_object('custom_greeting', custom_greeting, "
            "'agent_style_notes', agent_style_notes)"
        )
    else:
        op.execute(
            "UPDATE restaurants SET assistant_settings = "
            "json_object('custom_greeting', custom_greeting, "
            "'agent_style_notes', agent_style_notes)"
        )

    op.drop_column("restaurants", "agent_style_notes")
    op.drop_column("restaurants", "custom_greeting")
    op.drop_column("users", "token_valid_after")
