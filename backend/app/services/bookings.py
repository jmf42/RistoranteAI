from __future__ import annotations

from datetime import date, time
from typing import Any

from sqlalchemy import Select, asc, select
from sqlalchemy.orm import Session

from app.core.security import decrypt_pii_or_fallback, encrypt_pii, hash_phone, normalize_phone
from app.models import Booking, BookingEvent, Customer, Restaurant, User
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.schemas.common import BookingStatus
from app.services.availability import ACTIVE_STATUSES, check_availability


def restaurant_initials(name: str) -> str:
    parts = [piece[0] for piece in name.split() if piece]
    return "".join(parts[:2]).upper() or "RA"


def lock_restaurant(db: Session, restaurant_id: str) -> Restaurant | None:
    stmt: Select[tuple[Restaurant]] = (
        select(Restaurant).where(Restaurant.id == restaurant_id).with_for_update()
    )
    restaurant = db.execute(stmt).scalar_one_or_none()
    return restaurant


def generate_confirmation_code(db: Session, restaurant: Restaurant, booking_date: date) -> str:
    prefix = restaurant_initials(restaurant.name)
    date_part = booking_date.strftime("%m%d")
    counter = 1
    while True:
        candidate = f"{prefix}-{date_part}{counter:02d}"
        exists = db.scalar(select(Booking.id).where(Booking.confirmation_code == candidate))
        if not exists:
            return candidate
        counter += 1


def booking_to_read(booking: Booking) -> BookingRead:
    return BookingRead(
        id=booking.id,
        restaurant_id=booking.restaurant_id,
        confirmation_code=booking.confirmation_code,
        date=booking.date,
        time=booking.time,
        turno=booking.turno,
        party_size=booking.party_size,
        customer_name=decrypt_pii_or_fallback(booking.customer_name_encrypted),
        customer_phone=decrypt_pii_or_fallback(booking.customer_phone_encrypted),
        special_requests=booking.special_requests,
        status=booking.status,
        source=booking.source,
        customer_id=booking.customer_id,
        created_at=booking.created_at.isoformat(),
        updated_at=booking.updated_at.isoformat(),
    )


def find_turno_name(restaurant: Restaurant, booking_time: time) -> str:
    for turno in restaurant.turni:
        start = time.fromisoformat(turno["start"])
        end = time.fromisoformat(turno["end"])
        if start <= booking_time < end:
            return turno["name"]
    raise ValueError("Requested time is outside configured turni")


# ---------------------------------------------------------------------------
# Customer upsert
# ---------------------------------------------------------------------------


def upsert_customer(
    db: Session,
    *,
    restaurant_id: str,
    phone_hash: str,
    name_encrypted: str,
    phone_encrypted: str,
    booking_date: date,
) -> Customer:
    customer = db.scalar(
        select(Customer).where(
            Customer.restaurant_id == restaurant_id,
            Customer.phone_hash == phone_hash,
        )
    )
    if customer:
        customer.name_encrypted = name_encrypted
        customer.booking_count += 1
        customer.last_booking_date = booking_date
    else:
        customer = Customer(
            restaurant_id=restaurant_id,
            phone_hash=phone_hash,
            name_encrypted=name_encrypted,
            phone_encrypted=phone_encrypted,
            booking_count=1,
            last_booking_date=booking_date,
        )
        db.add(customer)
    db.flush()
    return customer


def increment_customer_stat(db: Session, *, customer_id: str | None, stat: str) -> None:
    if not customer_id:
        return
    customer = db.get(Customer, customer_id)
    if not customer:
        return
    if stat == "cancellation":
        customer.cancellation_count += 1
    elif stat == "no_show":
        customer.no_show_count += 1


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def log_booking_event(
    db: Session,
    *,
    booking_id: str,
    event_type: str,
    changed_by: str | None = None,
    changes: dict[str, Any] | None = None,
) -> BookingEvent:
    event = BookingEvent(
        booking_id=booking_id,
        event_type=event_type,
        changed_by=changed_by,
        changes=changes or {},
    )
    db.add(event)
    return event


# ---------------------------------------------------------------------------
# Core booking operations
# ---------------------------------------------------------------------------


def create_booking(
    db: Session,
    *,
    payload: BookingCreate,
    changed_by: str | None = None,
) -> tuple[Booking | None, dict[str, Any] | None]:
    restaurant = lock_restaurant(db, payload.restaurant_id)
    if not restaurant:
        return None, {"reason": "restaurant_not_found", "alternatives": []}
    availability = check_availability(
        db,
        restaurant=restaurant,
        booking_date=payload.date,
        requested_time=payload.time,
        party_size=payload.party_size,
    )
    if not availability.get("open") or not availability.get("available"):
        reason = availability.get("reason") or "slot_just_filled"
        return None, {"reason": reason, "alternatives": availability.get("alternatives", [])}

    turno_name = availability["slot"]["turno"]
    confirmation_code = generate_confirmation_code(db, restaurant, payload.date)
    normalized_phone = normalize_phone(payload.customer_phone)
    phone_hash = hash_phone(normalized_phone)
    name_encrypted = encrypt_pii(payload.customer_name)
    phone_encrypted = encrypt_pii(normalized_phone)

    customer = upsert_customer(
        db,
        restaurant_id=restaurant.id,
        phone_hash=phone_hash,
        name_encrypted=name_encrypted,
        phone_encrypted=phone_encrypted,
        booking_date=payload.date,
    )

    booking = Booking(
        restaurant_id=restaurant.id,
        confirmation_code=confirmation_code,
        date=payload.date,
        time=payload.time,
        turno=turno_name,
        party_size=payload.party_size,
        customer_name_encrypted=name_encrypted,
        customer_phone_encrypted=phone_encrypted,
        customer_phone_hash=phone_hash,
        special_requests=payload.special_requests,
        status=str(payload.status),
        source=str(payload.source),
        customer_id=customer.id,
    )
    db.add(booking)
    db.flush()
    db.refresh(booking)

    log_booking_event(
        db,
        booking_id=booking.id,
        event_type="created",
        changed_by=changed_by or str(payload.source),
        changes={
            "date": payload.date.isoformat(),
            "time": payload.time.isoformat(),
            "party_size": payload.party_size,
            "turno": turno_name,
            "confirmation_code": confirmation_code,
        },
    )

    return booking, None


def list_bookings(
    db: Session,
    *,
    restaurant_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[BookingRead]:
    stmt = select(Booking).where(Booking.restaurant_id == restaurant_id)
    if date_from:
        stmt = stmt.where(Booking.date >= date_from)
    if date_to:
        stmt = stmt.where(Booking.date <= date_to)
    if status:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(asc(Booking.date), asc(Booking.time)).limit(limit)
    bookings = db.scalars(stmt).all()
    return [booking_to_read(booking) for booking in bookings]


def get_booking(db: Session, *, booking_id: str, restaurant_id: str | None = None) -> Booking | None:
    stmt = select(Booking).where(Booking.id == booking_id)
    if restaurant_id:
        stmt = stmt.where(Booking.restaurant_id == restaurant_id)
    booking = db.execute(stmt).scalar_one_or_none()
    return booking


def find_bookings_for_caller(
    db: Session,
    *,
    restaurant_id: str,
    caller_phone: str | None = None,
    confirmation_code: str | None = None,
) -> list[BookingRead]:
    stmt = select(Booking).where(
        Booking.restaurant_id == restaurant_id,
        Booking.status.in_(ACTIVE_STATUSES),
        Booking.date >= date.today(),
    )
    if caller_phone:
        stmt = stmt.where(Booking.customer_phone_hash == hash_phone(caller_phone))
    if confirmation_code:
        stmt = stmt.where(Booking.confirmation_code == confirmation_code)
    bookings = db.scalars(stmt.order_by(asc(Booking.date), asc(Booking.time))).all()
    return [booking_to_read(booking) for booking in bookings]


def update_booking(
    db: Session,
    *,
    booking: Booking,
    changes: BookingUpdate,
    changed_by: str | None = None,
) -> tuple[Booking | None, dict[str, Any] | None]:
    restaurant = lock_restaurant(db, booking.restaurant_id)
    if not restaurant:
        return None, {"reason": "restaurant_not_found", "alternatives": []}
    target_date = changes.date if changes.date is not None else booking.date
    target_time = changes.time if changes.time is not None else booking.time
    target_party_size = changes.party_size if changes.party_size is not None else booking.party_size

    availability = check_availability(
        db,
        restaurant=restaurant,
        booking_date=target_date,
        requested_time=target_time,
        party_size=target_party_size,
        exclude_booking_id=booking.id,
    )
    if not availability.get("open") or not availability.get("available"):
        reason = availability.get("reason") or "new_slot_unavailable"
        return None, {"reason": reason, "alternatives": availability.get("alternatives", [])}

    change_log: dict[str, Any] = {}
    if changes.date is not None and changes.date != booking.date:
        change_log["date"] = {"from": booking.date.isoformat(), "to": changes.date.isoformat()}
    if changes.time is not None and changes.time != booking.time:
        change_log["time"] = {"from": booking.time.isoformat(), "to": changes.time.isoformat()}
    if changes.party_size is not None and changes.party_size != booking.party_size:
        change_log["party_size"] = {"from": booking.party_size, "to": changes.party_size}
    if changes.status is not None and str(changes.status) != booking.status:
        change_log["status"] = {
            "from": booking.status,
            "to": str(changes.status),
        }

    booking.date = target_date
    booking.time = target_time
    booking.party_size = target_party_size
    booking.turno = availability["slot"]["turno"]
    if changes.customer_name is not None:
        booking.customer_name_encrypted = encrypt_pii(changes.customer_name)
        change_log["customer_name"] = "updated"
    if changes.customer_phone is not None:
        normalized_phone = normalize_phone(changes.customer_phone)
        booking.customer_phone_encrypted = encrypt_pii(normalized_phone)
        booking.customer_phone_hash = hash_phone(normalized_phone)
        change_log["customer_phone"] = "updated"
    if changes.special_requests is not None:
        booking.special_requests = changes.special_requests
    if changes.status is not None:
        booking.status = str(changes.status)
        if booking.status == "no_show":
            increment_customer_stat(db, customer_id=booking.customer_id, stat="no_show")
    elif change_log:
        booking.status = BookingStatus.modified
    db.add(booking)
    db.flush()
    db.refresh(booking)

    if change_log:
        log_booking_event(
            db,
            booking_id=booking.id,
            event_type="modified",
            changed_by=changed_by,
            changes=change_log,
        )

    return booking, None


def cancel_booking(
    db: Session,
    *,
    booking: Booking,
    changed_by: str | None = None,
) -> Booking:
    previous_status = booking.status
    booking.status = BookingStatus.cancelled
    db.add(booking)
    db.flush()

    log_booking_event(
        db,
        booking_id=booking.id,
        event_type="cancelled",
        changed_by=changed_by,
        changes={"status": {"from": previous_status, "to": "cancelled"}},
    )
    increment_customer_stat(db, customer_id=booking.customer_id, stat="cancellation")

    db.refresh(booking)
    return booking


def ensure_default_users(db: Session, users: list[User]) -> None:
    for user in users:
        db.add(user)
    db.commit()
