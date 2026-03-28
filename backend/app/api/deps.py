from __future__ import annotations

from collections.abc import Generator

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.observability import json_log
from app.core.security import decode_access_token
from app.models import Restaurant, User, UserRestaurant


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _token_from_request(request: Request) -> str | None:
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1)
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    user = db.scalar(select(User).where(User.id == payload["sub"], User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # Reject tokens issued before token_valid_after (password change, revocation)
    if user.token_valid_after:
        issued_at = payload.get("iat", 0)
        if issued_at < user.token_valid_after.timestamp():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return user


def require_roles(*roles: str):
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return current_user

    return _dependency


def _user_accessible_restaurant_ids(db: Session, user: User) -> set[str]:
    ids: set[str] = set()
    if user.restaurant_id:
        ids.add(user.restaurant_id)
    linked = db.scalars(
        select(UserRestaurant.restaurant_id).where(UserRestaurant.user_id == user.id)
    ).all()
    ids.update(linked)
    return ids


def accessible_restaurant_id(
    db: Session,
    *,
    current_user: User,
    restaurant_id: str | None,
) -> str:
    if current_user.role == "operator":
        if restaurant_id:
            return restaurant_id
        restaurant = db.scalar(
            select(Restaurant).where(Restaurant.is_active.is_(True)).order_by(Restaurant.name)
        )
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No restaurants configured")
        return restaurant.id

    allowed_ids = _user_accessible_restaurant_ids(db, current_user)
    if not allowed_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner has no restaurant")
    if restaurant_id:
        if restaurant_id not in allowed_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access denied")
        return restaurant_id
    return next(iter(allowed_ids))


def get_restaurant_or_404(db: Session, restaurant_id: str) -> Restaurant:
    restaurant = db.scalar(select(Restaurant).where(Restaurant.id == restaurant_id))
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return restaurant


def verify_tool_secret(request: Request) -> None:
    secret = request.headers.get(settings.tool_secret_header_name)
    if secret != settings.elevenlabs_tool_secret:
        received_hint = f"{secret[:4]}…" if secret and len(secret) > 4 else "(missing)"
        expected_hint = f"{settings.elevenlabs_tool_secret[:4]}…"
        json_log(
            "app.security",
            {
                "event": "tool_auth_failed",
                "path": str(request.url.path),
                "header": settings.tool_secret_header_name,
                "received_prefix": received_hint,
                "expected_prefix": expected_hint,
                "client": request.client.host if request.client else None,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tool secret")


# Personalization uses the same header but accepts both the dedicated personalization
# secret (if configured) and the general tool secret, so a single secret works for
# all ElevenLabs integrations unless explicitly separated.
def verify_personalization_secret(request: Request) -> None:
    secret = request.headers.get(settings.tool_secret_header_name)
    accepted = {settings.elevenlabs_tool_secret, settings.personalization_secret}
    if secret not in accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid personalization secret"
        )
