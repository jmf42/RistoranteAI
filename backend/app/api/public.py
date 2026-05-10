from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.observability import client_ip_for_request
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import decrypt_pii_or_fallback, encrypt_pii, hash_email, hash_phone
from app.models import Booking, Restaurant
from app.schemas.booking import BookingCreate, BookingUpdate
from app.schemas.common import BookingSource
from app.schemas.public import (
    OnlineBookingSettingsRead,
    PublicAvailabilityRequest,
    PublicAvailabilityResponse,
    PublicBookingCreateRequest,
    PublicBookingCreateResponse,
    PublicBookingModifyRequest,
    PublicBookingReadResponse,
    PublicReservationConfigResponse,
    PublicRestaurantSummary,
)
from app.services.availability import check_availability
from app.services.bookings import booking_to_read, cancel_booking, create_booking, update_booking
from app.services.notifications import deliver_notification_batch, queue_booking_email
from app.services.public_reservations import (
    booking_from_manage_token,
    cutoff_allows_action,
    enforce_public_booking_rules,
    get_public_restaurant_or_404,
    issue_manage_token,
    manage_url_for_token,
    resolved_online_booking_settings,
)

router = APIRouter(prefix="/public", tags=["public"])
contact_limiter = InMemoryRateLimiter()


def _apply_contact_limit(*, key: str, limit: int = 6, window_seconds: int = 300) -> None:
    allowed, retry_after = contact_limiter.allow(key=key, limit=limit, window_seconds=window_seconds)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many reservation attempts. Please wait and try again.",
        headers={"Retry-After": str(retry_after)},
    )


def _manage_url_from_booking(booking: Booking, *, request: Request) -> str:
    encrypted_token = (booking.channel_metadata or {}).get("manage_token")
    raw_token = decrypt_pii_or_fallback(str(encrypted_token), fallback="") if encrypted_token else ""
    if not raw_token:
        return ""
    request_origin = str(request.headers.get("origin") or "").strip() or str(request.base_url).rstrip("/")
    return manage_url_for_token(raw_token, request_origin)


def _booking_permissions(booking: Booking, *, restaurant) -> tuple[bool, bool]:
    settings = resolved_online_booking_settings(restaurant)
    can_modify = cutoff_allows_action(
        booking=booking,
        restaurant=restaurant,
        hours_before=int(settings["modify_cutoff_hours"]),
    )
    can_cancel = cutoff_allows_action(
        booking=booking,
        restaurant=restaurant,
        hours_before=int(settings["cancel_cutoff_hours"]),
    )
    return can_modify, can_cancel


@router.get("/restaurants/{slug}/reservation-config", response_model=PublicReservationConfigResponse)
def reservation_config(slug: str, db: Session = Depends(get_db)) -> PublicReservationConfigResponse:
    restaurant = get_public_restaurant_or_404(db, slug)
    return PublicReservationConfigResponse(
        restaurant=PublicRestaurantSummary(
            name=restaurant.name,
            slug=restaurant.slug,
            timezone=restaurant.timezone,
            address=restaurant.address,
        ),
        online_booking=OnlineBookingSettingsRead(**resolved_online_booking_settings(restaurant)),
        turni=restaurant.turni,
    )


@router.post("/restaurants/{slug}/availability", response_model=PublicAvailabilityResponse)
def reservation_availability(
    slug: str,
    payload: PublicAvailabilityRequest,
    db: Session = Depends(get_db),
) -> PublicAvailabilityResponse:
    restaurant = get_public_restaurant_or_404(db, slug)
    enforce_public_booking_rules(restaurant, party_size=payload.party_size)
    result = check_availability(
        db,
        restaurant=restaurant,
        booking_date=payload.date,
        requested_time=payload.time,
        party_size=payload.party_size,
    )
    return PublicAvailabilityResponse(restaurant_slug=restaurant.slug, result=result)


@router.post(
    "/restaurants/{slug}/bookings",
    response_model=PublicBookingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_public_booking(
    slug: str,
    payload: PublicBookingCreateRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PublicBookingCreateResponse:
    restaurant = get_public_restaurant_or_404(db, slug)
    enforce_public_booking_rules(restaurant, party_size=payload.party_size)

    settings_config = resolved_online_booking_settings(restaurant)
    if settings_config.get("require_email") and not payload.customer_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email address is required for online bookings.",
        )

    email_fragment = hash_email(str(payload.customer_email)) if payload.customer_email else "-"
    phone_fragment = hash_phone(payload.customer_phone)
    ip_fragment = client_ip_for_request(request)
    contact_key = f"{restaurant.id}:{phone_fragment}:{email_fragment}:{ip_fragment}"
    _apply_contact_limit(key=contact_key)

    if idempotency_key:
        existing = db.scalar(
            select(Booking).where(
                Booking.restaurant_id == restaurant.id,
                Booking.source == BookingSource.web,
                Booking.idempotency_key == idempotency_key,
            )
        )
        if existing:
            response.status_code = status.HTTP_200_OK
            return PublicBookingCreateResponse(
                booking=booking_to_read(existing),
                manage_url=_manage_url_from_booking(existing, request=request),
                notification_status="already_confirmed",
            )

    booking_payload = BookingCreate(
        restaurant_id=restaurant.id,
        date=payload.date,
        time=payload.time,
        party_size=payload.party_size,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        special_requests=payload.special_requests,
        source=BookingSource.web,
        channel_metadata={
            "actor": "guest_web",
            "restaurant_slug": restaurant.slug,
            "request_ip": client_ip_for_request(request),
        },
        idempotency_key=idempotency_key,
    )
    booking, error = create_booking(db, payload=booking_payload, changed_by="guest:web")
    if error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
    assert booking is not None

    raw_manage_token = issue_manage_token(db, booking=booking)
    booking.channel_metadata = {
        **(booking.channel_metadata or {}),
        "manage_token": encrypt_pii(raw_manage_token),
    }
    db.add(booking)
    manage_url = manage_url_for_token(
        raw_manage_token,
        request.headers.get("origin") or str(request.base_url).rstrip("/"),
    )
    queued_notification = queue_booking_email(
        db,
        booking=booking,
        template_key="booking_confirmation",
        manage_url=manage_url,
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not idempotency_key:
            raise
        existing = db.scalar(
            select(Booking).where(
                Booking.restaurant_id == restaurant.id,
                Booking.source == BookingSource.web,
                Booking.idempotency_key == idempotency_key,
            )
        )
        if not existing:
            raise
        response.status_code = status.HTTP_200_OK
        return PublicBookingCreateResponse(
            booking=booking_to_read(existing),
            manage_url=_manage_url_from_booking(existing, request=request),
            notification_status="already_confirmed",
        )

    db.refresh(booking)
    background_tasks.add_task(deliver_notification_batch)
    return PublicBookingCreateResponse(
        booking=booking_to_read(booking),
        manage_url=manage_url,
        notification_status="queued" if queued_notification is not None else "skipped",
    )


@router.get("/bookings/{manage_token}", response_model=PublicBookingReadResponse)
def public_booking_detail(
    manage_token: str,
    db: Session = Depends(get_db),
) -> PublicBookingReadResponse:
    _, booking = booking_from_manage_token(db, manage_token)
    restaurant = db.get(Restaurant, booking.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    db.commit()
    can_modify, can_cancel = _booking_permissions(booking, restaurant=restaurant)
    return PublicBookingReadResponse(
        booking=booking_to_read(booking),
        can_modify=can_modify,
        can_cancel=can_cancel,
    )


@router.post("/bookings/{manage_token}/modify", response_model=PublicBookingReadResponse)
def modify_public_booking(
    manage_token: str,
    payload: PublicBookingModifyRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicBookingReadResponse:
    _, booking = booking_from_manage_token(db, manage_token)
    restaurant = db.get(Restaurant, booking.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    can_modify, can_cancel = _booking_permissions(booking, restaurant=restaurant)
    if not can_modify:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking can no longer be modified online")
    next_party_size = payload.party_size if payload.party_size is not None else booking.party_size
    enforce_public_booking_rules(restaurant, party_size=next_party_size)
    updated, error = update_booking(
        db,
        booking=booking,
        changes=BookingUpdate(**payload.model_dump(exclude_unset=True)),
        changed_by="guest:web",
    )
    if error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
    assert updated is not None
    manage_url = _manage_url_from_booking(updated, request=request)
    queue_booking_email(db, booking=updated, template_key="booking_modified", manage_url=manage_url)
    db.commit()
    db.refresh(updated)
    background_tasks.add_task(deliver_notification_batch)
    return PublicBookingReadResponse(
        booking=booking_to_read(updated),
        can_modify=can_modify,
        can_cancel=can_cancel,
    )


@router.post("/bookings/{manage_token}/cancel", response_model=PublicBookingReadResponse)
def cancel_public_booking(
    manage_token: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicBookingReadResponse:
    _, booking = booking_from_manage_token(db, manage_token)
    restaurant = db.get(Restaurant, booking.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    _, can_cancel = _booking_permissions(booking, restaurant=restaurant)
    if not can_cancel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking can no longer be cancelled online")
    cancelled = cancel_booking(db, booking=booking, changed_by="guest:web")
    manage_url = _manage_url_from_booking(cancelled, request=request)
    queue_booking_email(db, booking=cancelled, template_key="booking_cancelled", manage_url=manage_url)
    db.commit()
    db.refresh(cancelled)
    background_tasks.add_task(deliver_notification_batch)
    return PublicBookingReadResponse(
        booking=booking_to_read(cancelled),
        can_modify=False,
        can_cancel=False,
    )
