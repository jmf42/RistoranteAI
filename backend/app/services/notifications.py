from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt_pii_or_fallback
from app.models import Booking, NotificationOutbox


def queue_booking_email(
    db,
    *,
    booking: Booking,
    template_key: str,
    manage_url: str,
) -> NotificationOutbox | None:
    if not booking.customer_email_encrypted:
        return None
    recipient = decrypt_pii_or_fallback(booking.customer_email_encrypted, fallback="")
    if not recipient:
        return None

    subjects = {
        "booking_confirmation": f"Prenotazione confermata {booking.confirmation_code}",
        "booking_modified": f"Prenotazione aggiornata {booking.confirmation_code}",
        "booking_cancelled": f"Prenotazione cancellata {booking.confirmation_code}",
    }
    intro = {
        "booking_confirmation": "La tua prenotazione e' confermata.",
        "booking_modified": "La tua prenotazione e' stata aggiornata.",
        "booking_cancelled": "La tua prenotazione e' stata cancellata.",
    }
    payload = {
        "confirmation_code": booking.confirmation_code,
        "date": booking.date.isoformat(),
        "time": booking.time.strftime("%H:%M"),
        "party_size": booking.party_size,
        "manage_url": manage_url,
        "status": booking.status,
        "body_text": (
            f"{intro[template_key]}\n\n"
            f"Codice: {booking.confirmation_code}\n"
            f"Data: {booking.date.isoformat()}\n"
            f"Ora: {booking.time.strftime('%H:%M')}\n"
            f"Coperti: {booking.party_size}\n\n"
            f"Gestisci la prenotazione: {manage_url}\n"
        ),
    }
    notification = NotificationOutbox(
        restaurant_id=booking.restaurant_id,
        booking_id=booking.id,
        channel="email",
        template_key=template_key,
        provider="smtp",
        recipient=recipient,
        subject=subjects[template_key],
        payload=payload,
        status="queued",
    )
    db.add(notification)
    db.flush()
    return notification


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.notification_from_email)


def _send_email(notification: NotificationOutbox) -> None:
    message = EmailMessage()
    message["From"] = settings.notification_from_email
    message["To"] = notification.recipient
    message["Subject"] = notification.subject
    message.set_content(str(notification.payload.get("body_text", "")))

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)


def deliver_notification_batch(*, limit: int = 20) -> None:
    db = SessionLocal()
    try:
        notifications = db.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status.in_(("queued", "retry")),
                NotificationOutbox.available_at <= datetime.now(UTC),
            )
            .order_by(NotificationOutbox.created_at.asc())
            .limit(limit)
        ).all()
        for notification in notifications:
            notification.attempt_count += 1
            if not _smtp_configured():
                notification.status = "failed"
                notification.last_error = "SMTP not configured"
                db.add(notification)
                continue
            try:
                _send_email(notification)
            except Exception as exc:  # noqa: BLE001
                notification.status = "failed"
                notification.last_error = str(exc)
            else:
                notification.status = "sent"
                notification.sent_at = datetime.now(UTC)
                notification.last_error = None
            db.add(notification)
        db.commit()
    finally:
        db.close()
