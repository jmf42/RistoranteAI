"""Enable RLS on public tables for Supabase exposure safety.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PUBLIC_TABLES = (
    "restaurants",
    "users",
    "bookings",
    "call_logs",
    "raw_webhook_events",
    "customers",
    "booking_events",
    "user_restaurants",
)

BACKEND_ROLES = (
    ("postgres", "rls_backend_full_access_postgres"),
    ("service_role", "rls_backend_full_access_service_role"),
)

PUBLIC_API_ROLES = ("anon", "authenticated")


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _role_exists(role_name: str) -> bool:
    query = sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role_name")
    return bool(op.get_bind().execute(query, {"role_name": role_name}).scalar())


def _policy_exists(table_name: str, policy_name: str) -> bool:
    query = sa.text(
        """
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = :table_name
          AND policyname = :policy_name
        """
    )
    return bool(
        op.get_bind().execute(
            query,
            {"table_name": table_name, "policy_name": policy_name},
        ).scalar()
    )


def upgrade() -> None:
    if not _is_postgresql():
        return

    for table_name in PUBLIC_TABLES:
        op.execute(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY')

        for role_name, policy_name in BACKEND_ROLES:
            if not _role_exists(role_name):
                continue
            if _policy_exists(table_name, policy_name):
                continue
            op.execute(
                f'CREATE POLICY "{policy_name}" ON public."{table_name}" '
                f'FOR ALL TO "{role_name}" USING (true) WITH CHECK (true)'
            )

    for role_name in PUBLIC_API_ROLES:
        if not _role_exists(role_name):
            continue
        op.execute(f'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM "{role_name}"')
        op.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM "{role_name}"')

    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC")


def downgrade() -> None:
    if not _is_postgresql():
        return

    for table_name in PUBLIC_TABLES:
        for _, policy_name in BACKEND_ROLES:
            if _policy_exists(table_name, policy_name):
                op.execute(f'DROP POLICY "{policy_name}" ON public."{table_name}"')
        op.execute(f'ALTER TABLE public."{table_name}" DISABLE ROW LEVEL SECURITY')
