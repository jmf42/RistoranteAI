from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_restaurant_or_404, verify_tool_secret
from app.core.observability import json_log
from app.models import Booking
from app.schemas.booking import BookingCreate, BookingUpdate
from app.schemas.common import BookingSource, BookingStatus
from app.schemas.tools import (
    CancelBookingRequest,
    CancelBookingResponse,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    CreateBookingToolRequest,
    CreateBookingToolResponse,
    FindBookingRequest,
    FindBookingResponse,
    ModifyBookingRequest,
    ModifyBookingResponse,
)
from app.services.availability import ACTIVE_STATUSES, check_availability
from app.services.bookings import (
    booking_to_read,
    cancel_booking,
    create_booking,
    find_bookings_for_caller,
    update_booking,
)

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(verify_tool_secret)])


@router.post("/check-availability", response_model=CheckAvailabilityResponse)
def check_availability_route(
    payload: CheckAvailabilityRequest,
    db: Session = Depends(get_db),
) -> CheckAvailabilityResponse:
    restaurant = get_restaurant_or_404(db, payload.restaurant_id)
    result = check_availability(
        db,
        restaurant=restaurant,
        booking_date=payload.date,
        requested_time=payload.time_preference,
        party_size=payload.party_size,
    )
    return CheckAvailabilityResponse(**result)


@router.post("/create-booking", response_model=CreateBookingToolResponse)
def create_booking_tool(
    payload: CreateBookingToolRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CreateBookingToolResponse:
    get_restaurant_or_404(db, payload.restaurant_id)
    booking_payload = BookingCreate(
        restaurant_id=payload.restaurant_id,
        date=payload.date,
        time=payload.time,
        party_size=payload.party_size,
        customer_name=payload.customer_name,
        customer_phone=payload.caller_phone or payload.customer_phone,
        special_requests=payload.special_requests,
        source=BookingSource.ai_phone,
        status=BookingStatus.confirmed,
    )
    booking, error = create_booking(db, payload=booking_payload, changed_by="ai_phone")
    if error:
        db.rollback()
        json_log(
            "app.tools",
            {
                "event": "tool_create_booking_rejected",
                "request_id": getattr(request.state, "request_id", None),
                "restaurant_id": payload.restaurant_id,
                "reason": error["reason"],
            },
        )
        return CreateBookingToolResponse(success=False, reason=error["reason"], alternatives=error["alternatives"])
    db.commit()
    db.refresh(booking)
    json_log(
        "app.tools",
        {
            "event": "tool_create_booking_success",
            "request_id": getattr(request.state, "request_id", None),
            "restaurant_id": payload.restaurant_id,
            "booking_id": booking.id,
            "confirmation_code": booking.confirmation_code,
        },
    )
    return CreateBookingToolResponse(success=True, confirmation_code=booking.confirmation_code)


@router.post("/find-booking", response_model=FindBookingResponse)
def find_booking_tool(payload: FindBookingRequest, db: Session = Depends(get_db)) -> FindBookingResponse:
    bookings = find_bookings_for_caller(
        db,
        restaurant_id=payload.restaurant_id,
        caller_phone=payload.caller_phone,
        confirmation_code=payload.confirmation_code,
    )
    return FindBookingResponse(
        found=bool(bookings),
        bookings=[
            {
                "confirmation_code": booking.confirmation_code,
                "date": str(booking.date),
                "time": str(booking.time),
                "party_size": booking.party_size,
                "name": booking.customer_name,
                "status": str(booking.status),
            }
            for booking in bookings
        ],
    )


@router.post("/modify-booking", response_model=ModifyBookingResponse)
def modify_booking_tool(
    payload: ModifyBookingRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ModifyBookingResponse:
    stmt = select(Booking).where(
        Booking.confirmation_code == payload.confirmation_code,
        Booking.status.in_(ACTIVE_STATUSES),
    )
    if payload.restaurant_id:
        stmt = stmt.where(Booking.restaurant_id == payload.restaurant_id)
    booking = db.scalar(stmt)
    if not booking:
        return ModifyBookingResponse(success=False, reason="Prenotazione non trovata.")
    updated, error = update_booking(
        db,
        booking=booking,
        changes=BookingUpdate(**payload.changes.model_dump(exclude_unset=True)),
        changed_by="ai_phone",
    )
    if error:
        db.rollback()
        json_log(
            "app.tools",
            {
                "event": "tool_modify_booking_rejected",
                "request_id": getattr(request.state, "request_id", None),
                "confirmation_code": payload.confirmation_code,
                "reason": error["reason"],
            },
        )
        return ModifyBookingResponse(
            success=False,
            reason=error["reason"],
            alternatives=error["alternatives"],
        )
    db.commit()
    db.refresh(updated)
    json_log(
        "app.tools",
        {
            "event": "tool_modify_booking_success",
            "request_id": getattr(request.state, "request_id", None),
            "booking_id": updated.id,
            "confirmation_code": updated.confirmation_code,
        },
    )
    return ModifyBookingResponse(success=True, updated_booking=booking_to_read(updated).model_dump())


@router.post("/cancel-booking", response_model=CancelBookingResponse)
def cancel_booking_tool(
    payload: CancelBookingRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CancelBookingResponse:
    stmt = select(Booking).where(
        Booking.confirmation_code == payload.confirmation_code,
        Booking.status.in_(ACTIVE_STATUSES),
    )
    if payload.restaurant_id:
        stmt = stmt.where(Booking.restaurant_id == payload.restaurant_id)
    booking = db.scalar(stmt)
    if not booking:
        return CancelBookingResponse(success=False)
    cancel_booking(db, booking=booking, changed_by="ai_phone")
    db.commit()
    json_log(
        "app.tools",
        {
            "event": "tool_cancel_booking_success",
            "request_id": getattr(request.state, "request_id", None),
            "booking_id": booking.id,
            "confirmation_code": booking.confirmation_code,
        },
    )
    return CancelBookingResponse(success=True)
