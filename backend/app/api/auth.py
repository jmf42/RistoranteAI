from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import clear_auth_cookie, create_access_token, set_auth_cookie, verify_password
from app.models import User, UserRestaurant
from app.schemas.auth import LoginRequest, SessionResponse, SessionUser

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_session_user(db: Session, user: User) -> SessionUser:
    linked_ids = list(
        db.scalars(
            select(UserRestaurant.restaurant_id).where(UserRestaurant.user_id == user.id)
        ).all()
    )
    all_ids: set[str] = set(linked_ids)
    if user.restaurant_id:
        all_ids.add(user.restaurant_id)
    return SessionUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        restaurant_id=user.restaurant_id,
        restaurant_ids=sorted(all_ids),
    )


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> SessionResponse:
    stmt = select(User).where(func.lower(User.email) == payload.email.lower(), User.is_active.is_(True))
    user = db.scalar(stmt)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        restaurant_id=user.restaurant_id,
    )
    set_auth_cookie(response, token)
    return SessionResponse(user=_build_session_user(db, user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


@router.get("/me", response_model=SessionResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SessionResponse:
    return SessionResponse(user=_build_session_user(db, current_user))
