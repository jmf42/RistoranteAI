from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def default_opening_hours() -> dict[str, str]:
    return {"lunch": "12:00-15:00", "dinner": "19:00-23:00"}


def default_turni() -> list[dict[str, Any]]:
    return [
        {"name": "Cena 1", "start": "19:00", "end": "21:00", "max_covers": 40},
        {"name": "Cena 2", "start": "21:00", "end": "23:30", "max_covers": 35},
    ]


def default_booking_rules() -> dict[str, int]:
    return {
        "min_party": 1,
        "max_party": 20,
        "large_group_threshold": 8,
        "max_advance_days": 60,
        "min_lead_hours": 2,
    }


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    twilio_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    elevenlabs_agent_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Rome")
    address: Mapped[str] = mapped_column(String(300))
    opening_hours: Mapped[dict[str, Any]] = mapped_column(JSON, default=default_opening_hours)
    weekly_closures: Mapped[list[str]] = mapped_column(JSON, default=list)
    closure_dates: Mapped[list[str]] = mapped_column(JSON, default=list)
    turni: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=default_turni)
    booking_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=default_booking_rules)
    custom_greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_style_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="Warm, concise, premium Italian hospitality tone."
    )
    escalation_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    bookings: Mapped[list[Booking]] = relationship(back_populates="restaurant")
    call_logs: Mapped[list[CallLog]] = relationship(back_populates="restaurant")
    users: Mapped[list[User]] = relationship(back_populates="restaurant")
    customers: Mapped[list[Customer]] = relationship(back_populates="restaurant", viewonly=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    password_hash: Mapped[str] = mapped_column(Text)
    restaurant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("restaurants.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    restaurant: Mapped[Restaurant | None] = relationship(back_populates="users")
    restaurant_links: Mapped[list[UserRestaurant]] = relationship(back_populates="user")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "ix_bookings_restaurant_date_status_turno",
            "restaurant_id",
            "date",
            "status",
            "turno",
        ),
        Index(
            "ix_bookings_restaurant_date_time_party_phone_status_created",
            "restaurant_id",
            "date",
            "time",
            "party_size",
            "customer_phone_hash",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurants.id"), index=True)
    confirmation_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    date: Mapped[Any] = mapped_column(Date, index=True)
    time: Mapped[Any] = mapped_column(Time, nullable=False)
    turno: Mapped[str] = mapped_column(String(40), index=True)
    party_size: Mapped[int] = mapped_column(Integer)
    customer_name_encrypted: Mapped[str] = mapped_column(Text)
    customer_phone_encrypted: Mapped[str] = mapped_column(Text)
    customer_phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    source: Mapped[str] = mapped_column(String(20), default="dashboard")
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="bookings")
    call_logs: Mapped[list[CallLog]] = relationship(back_populates="booking")
    customer: Mapped[Customer | None] = relationship(back_populates="bookings")
    events: Mapped[list[BookingEvent]] = relationship(back_populates="booking", order_by="BookingEvent.created_at")


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurants.id"), index=True)
    elevenlabs_conversation_id: Mapped[str | None] = mapped_column(
        String(120), unique=True, nullable=True, index=True
    )
    caller_phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(40), default="info_provided", index=True)
    call_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    booking_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    transcript_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    restaurant: Mapped[Restaurant] = relationship(back_populates="call_logs")
    booking: Mapped[Booking | None] = relationship(back_populates="call_logs")


class RawWebhookEvent(Base):
    __tablename__ = "raw_webhook_events"
    __table_args__ = (
        UniqueConstraint("source", "event_key", name="uq_raw_webhook_events_source_event_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source: Mapped[str] = mapped_column(String(40), index=True)
    event_key: Mapped[str] = mapped_column(String(120))
    restaurant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("restaurants.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    restaurant: Mapped[Restaurant | None] = relationship()


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurants.id"), index=True)
    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    name_encrypted: Mapped[str] = mapped_column(Text)
    phone_encrypted: Mapped[str] = mapped_column(Text)
    booking_count: Mapped[int] = mapped_column(Integer, default=0)
    no_show_count: Mapped[int] = mapped_column(Integer, default=0)
    cancellation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_booking_date: Mapped[Any] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("restaurant_id", "phone_hash", name="uq_customers_restaurant_phone"),
        {"comment": "Customer profiles built from booking history"},
    )

    restaurant: Mapped[Restaurant] = relationship()
    bookings: Mapped[list[Booking]] = relationship(back_populates="customer")


class BookingEvent(Base):
    __tablename__ = "booking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    booking: Mapped[Booking] = relationship(back_populates="events")


class UserRestaurant(Base):
    __tablename__ = "user_restaurants"
    __table_args__ = (UniqueConstraint("user_id", "restaurant_id", name="uq_user_restaurants_user_restaurant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurants.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="restaurant_links")
    restaurant: Mapped[Restaurant] = relationship()
