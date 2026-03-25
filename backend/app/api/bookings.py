from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import accessible_restaurant_id, get_current_user, get_db, get_restaurant_or_404
from app.models import BookingEvent, User
from app.schemas.booking import BookingCreate, BookingEventRead, BookingRead, BookingUpdate
from app.services.bookings import (
    booking_to_read,
    cancel_booking,
    create_booking,
    get_booking,
    list_bookings,
    update_booking,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _event_to_read(event: BookingEvent) -> BookingEventRead:
    return BookingEventRead(
        id=event.id,
        booking_id=event.booking_id,
        event_type=event.event_type,
        changed_by=event.changed_by,
        changes=event.changes or {},
        created_at=event.created_at.isoformat(),
    )


@router.get("", response_model=list[BookingRead])
def list_bookings_route(
    restaurant_id: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingRead]:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    return list_bookings(
        db,
        restaurant_id=resolved_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        limit=limit,
    )


@router.get("/export")
def export_bookings_route(
    restaurant_id: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    bookings = list_bookings(
        db,
        restaurant_id=resolved_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        limit=limit,
    )
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "confirmation_code",
            "date",
            "time",
            "turno",
            "party_size",
            "customer_name",
            "customer_phone",
            "status",
            "source",
            "special_requests",
            "created_at",
            "updated_at",
        ]
    )
    for booking in bookings:
        writer.writerow(
            [
                booking.confirmation_code,
                booking.date.isoformat(),
                booking.time.isoformat(),
                booking.turno,
                booking.party_size,
                booking.customer_name,
                booking.customer_phone,
                booking.status,
                booking.source,
                booking.special_requests or "",
                booking.created_at,
                booking.updated_at,
            ]
        )
    filename = f"bookings-{datetime.now(UTC).date().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking_route(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    resolved_id = accessible_restaurant_id(
        db, current_user=current_user, restaurant_id=payload.restaurant_id
    )
    get_restaurant_or_404(db, resolved_id)
    booking, error = create_booking(
        db,
        payload=payload.model_copy(update={"restaurant_id": resolved_id}),
        changed_by=f"user:{current_user.email}",
    )
    if error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking conflicts with existing data",
        ) from exc
    db.refresh(booking)
    return booking_to_read(booking)


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking_route(
    booking_id: str,
    payload: BookingUpdate,
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    booking = get_booking(db, booking_id=booking_id, restaurant_id=resolved_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    updated, error = update_booking(db, booking=booking, changes=payload, changed_by=f"user:{current_user.email}")
    if error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking update conflicts with existing data",
        ) from exc
    db.refresh(updated)
    return booking_to_read(updated)


@router.get("/{booking_id}/events", response_model=list[BookingEventRead])
def booking_events_route(
    booking_id: str,
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingEventRead]:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    booking = get_booking(db, booking_id=booking_id, restaurant_id=resolved_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    events = db.scalars(
        select(BookingEvent)
        .where(BookingEvent.booking_id == booking.id)
        .order_by(BookingEvent.created_at.desc())
    ).all()
    return [_event_to_read(event) for event in events]


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking_route(
    booking_id: str,
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    resolved_id = accessible_restaurant_id(db, current_user=current_user, restaurant_id=restaurant_id)
    booking = get_booking(db, booking_id=booking_id, restaurant_id=resolved_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    cancelled = cancel_booking(db, booking=booking, changed_by=f"user:{current_user.email}")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancellation conflicts with existing data",
        ) from exc
    db.refresh(cancelled)
    return booking_to_read(cancelled)
