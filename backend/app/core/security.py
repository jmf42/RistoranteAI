from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import phonenumbers
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Response
from pwdlib import PasswordHash

from app.core.config import Settings, settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def _build_fernet_key(seed: str) -> bytes:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet(app_settings: Settings = settings) -> Fernet:
    configured = app_settings.pii_encryption_key
    if configured:
        key_bytes = configured.encode("utf-8")
        if len(key_bytes) != 44:
            key_bytes = _build_fernet_key(configured)
    else:
        key_bytes = _build_fernet_key(app_settings.jwt_secret)
    return Fernet(key_bytes)


def encrypt_pii(value: str, app_settings: Settings = settings) -> str:
    return get_fernet(app_settings).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_pii(value: str, app_settings: Settings = settings) -> str:
    return get_fernet(app_settings).decrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_pii_or_fallback(
    value: str,
    fallback: str = "Dato non disponibile",
    app_settings: Settings = settings,
) -> str:
    try:
        return decrypt_pii(value, app_settings)
    except InvalidToken:
        return fallback


def normalize_phone(phone_number: str, default_region: str | None = None) -> str:
    candidate = phone_number.strip()
    region = default_region or settings.default_phone_region
    try:
        parsed = phonenumbers.parse(candidate, region)
        if phonenumbers.is_possible_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return "".join(char for char in candidate if char.isdigit() or char == "+")


def hash_phone(phone_number: str) -> str:
    normalized = normalize_phone(phone_number)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    restaurant_id: str | None,
    app_settings: Settings = settings,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "restaurant_id": restaurant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=app_settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, app_settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, app_settings: Settings = settings) -> dict[str, Any]:
    return jwt.decode(token, app_settings.jwt_secret, algorithms=["HS256"])


def set_auth_cookie(response: Response, token: str, app_settings: Settings = settings) -> None:
    same_site = "none" if app_settings.session_cookie_secure else "lax"
    response.set_cookie(
        key=app_settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=app_settings.session_cookie_secure,
        samesite=same_site,
        max_age=app_settings.jwt_expires_minutes * 60,
        path="/",
    )


def clear_auth_cookie(response: Response, app_settings: Settings = settings) -> None:
    same_site = "none" if app_settings.session_cookie_secure else "lax"
    response.delete_cookie(
        app_settings.session_cookie_name,
        path="/",
        secure=app_settings.session_cookie_secure,
        samesite=same_site,
    )
