from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import Booking, CallLog, Restaurant, User
from app.schemas.booking import BookingCreate
from app.schemas.common import BookingSource, BookingStatus
from app.services.bookings import create_booking


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(Restaurant.id).limit(1))
    if existing:
        return

    restaurant = Restaurant(
        slug="trattoria-da-mario",
        name="Trattoria da Mario",
        twilio_phone="+390212345678",
        elevenlabs_agent_id="agent_demo_mario",
        timezone="Europe/Rome",
        address="Via Roma 42, 20121 Milano",
        opening_hours={"lunch": "12:00-15:00", "dinner": "19:00-23:30"},
        weekly_closures=["monday"],
        closure_dates=[],
        turni=[
            {"name": "primo", "start": "19:00", "end": "21:00", "max_covers": 40},
            {"name": "secondo", "start": "21:00", "end": "23:30", "max_covers": 35},
        ],
        booking_rules={
            "min_party": 1,
            "max_party": 20,
            "large_group_threshold": 8,
            "max_advance_days": 60,
            "min_lead_hours": 2,
        },
        assistant_settings={
            "llm_provider": "openai",
            "openai_model": "gpt-5-mini",
            "reasoning_effort": "minimal",
            "response_verbosity": "low",
            "custom_greeting": None,
            "agent_style_notes": "Warm, concise, premium Italian hospitality tone.",
        },
        escalation_phone="+390298765432",
    )
    db.add(restaurant)
    db.flush()

    operator = User(
        email="operator@ristorante.ai",
        full_name="Platform Operator",
        role="operator",
        password_hash=get_password_hash("demo-password"),
        restaurant_id=None,
    )
    owner = User(
        email="owner@trattoriamadonnina.it",
        full_name="Giulia Bianchi",
        role="owner",
        password_hash=get_password_hash("madonnina"),
        restaurant_id=restaurant.id,
    )
    db.add_all([operator, owner])
    db.flush()

    today = date.today()
    sample_bookings = [
        BookingCreate(
            restaurant_id=restaurant.id,
            date=today,
            time=time(19, 30),
            party_size=4,
            customer_name="Rossi",
            customer_phone="+393331234567",
            special_requests="Allergia al glutine",
            source=BookingSource.ai_phone,
            status=BookingStatus.confirmed,
        ),
        BookingCreate(
            restaurant_id=restaurant.id,
            date=today + timedelta(days=1),
            time=time(21, 0),
            party_size=2,
            customer_name="Ferri",
            customer_phone="+393339876543",
            special_requests="Compleanno",
            source=BookingSource.dashboard,
            status=BookingStatus.confirmed,
        ),
        BookingCreate(
            restaurant_id=restaurant.id,
            date=today + timedelta(days=2),
            time=time(20, 0),
            party_size=6,
            customer_name="Greco",
            customer_phone="+393330001111",
            special_requests="Seggiolone",
            source=BookingSource.walk_in,
            status=BookingStatus.confirmed,
        ),
    ]
    for payload in sample_bookings:
        booking, _ = create_booking(db, payload=payload)
        if booking:
            db.add(booking)
    db.flush()

    bookings = db.scalars(select(Booking).where(Booking.restaurant_id == restaurant.id)).all()
    first_booking_id = bookings[0].id if bookings else None
    now = datetime.now(UTC)
    call_logs = [
        CallLog(
            restaurant_id=restaurant.id,
            elevenlabs_conversation_id="conv_demo_1",
            caller_phone_hash="demohash1",
            started_at=now - timedelta(hours=2),
            duration_seconds=127,
            outcome="booking_created",
            booking_id=first_booking_id,
            summary="Prenotato tavolo per 4 persone alle 19:30 a nome Rossi.",
            transcript_preview="Cliente: Vorrei un tavolo per quattro stasera. Agente: Perfetto, confermo.",
            extra_data={"requested_slot_label": "Oggi 19:30"},
        ),
        CallLog(
            restaurant_id=restaurant.id,
            elevenlabs_conversation_id="conv_demo_2",
            caller_phone_hash="demohash2",
            started_at=now - timedelta(hours=5),
            duration_seconds=84,
            outcome="info_provided",
            summary="Informazioni su opzioni senza glutine e parcheggio.",
            transcript_preview="Cliente: Avete opzioni senza glutine? Agente: Sì, diverse.",
            extra_data={},
        ),
        CallLog(
            restaurant_id=restaurant.id,
            elevenlabs_conversation_id="conv_demo_3",
            caller_phone_hash="demohash3",
            started_at=now - timedelta(days=1, hours=1),
            duration_seconds=92,
            outcome="escalated",
            summary="Gruppo da 10 persone trasferito al ristorante.",
            transcript_preview="Cliente: Siamo in dieci. Agente: La passo subito a un collega.",
            extra_data={"requested_slot_label": "Sab 21:00"},
        ),
    ]
    db.add_all(call_logs)
    db.commit()
