from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import AppBaseModel, UserRole


class LoginRequest(AppBaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class SessionUser(AppBaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    restaurant_id: str | None = None
    restaurant_ids: list[str] = Field(default_factory=list)


class SessionResponse(AppBaseModel):
    user: SessionUser
