"""Add customers, booking_events, user_restaurants tables and customer_id on bookings.

Revision ID: 0002
Revises: 20260324_0001
Create Date: 2026-03-24
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "20260324_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("restaurant_id", sa.String(36), sa.ForeignKey("restaurants.id"), nullable=False, index=True),
        sa.Column("phone_hash", sa.String(64), nullable=False, index=True),
        sa.Column("name_encrypted", sa.Text(), nullable=False),
        sa.Column("phone_encrypted", sa.Text(), nullable=False),
        sa.Column("booking_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_show_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancellation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_booking_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        comment="Customer profiles built from booking history",
    )
    op.create_index(
        "ix_customers_restaurant_phone",
        "customers",
        ["restaurant_id", "phone_hash"],
        unique=True,
    )

    op.create_table(
        "booking_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("changed_by", sa.String(40), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "user_restaurants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("restaurant_id", sa.String(36), sa.ForeignKey("restaurants.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_user_restaurants_user_restaurant",
        "user_restaurants",
        ["user_id", "restaurant_id"],
        unique=True,
    )

    users_table = sa.table(
        "users",
        sa.column("id", sa.String(36)),
        sa.column("restaurant_id", sa.String(36)),
        sa.column("role", sa.String(20)),
    )
    user_restaurants_table = sa.table(
        "user_restaurants",
        sa.column("id", sa.String(36)),
        sa.column("user_id", sa.String(36)),
        sa.column("restaurant_id", sa.String(36)),
        sa.column("role", sa.String(20)),
    )
    connection = op.get_bind()
    existing_links = connection.execute(
        sa.select(users_table.c.id, users_table.c.restaurant_id, users_table.c.role).where(
            users_table.c.restaurant_id.is_not(None)
        )
    ).all()
    if existing_links:
        connection.execute(
            user_restaurants_table.insert(),
            [
                {
                    "id": str(uuid4()),
                    "user_id": row.id,
                    "restaurant_id": row.restaurant_id,
                    "role": row.role if row.role in {"owner", "operator"} else "owner",
                }
                for row in existing_links
            ],
        )

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("bookings") as batch_op:
            batch_op.add_column(sa.Column("customer_id", sa.String(36), nullable=True))
            batch_op.create_foreign_key(
                "fk_bookings_customer_id_customers",
                "customers",
                ["customer_id"],
                ["id"],
            )
            batch_op.create_index("ix_bookings_customer_id", ["customer_id"], unique=False)
    else:
        op.add_column(
            "bookings",
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        )
        op.create_index("ix_bookings_customer_id", "bookings", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_customer_id", table_name="bookings")
    op.drop_column("bookings", "customer_id")
    op.drop_table("user_restaurants")
    op.drop_table("booking_events")
    op.drop_table("customers")
