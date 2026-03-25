from fastapi import Response

from app.core.config import Settings
from app.core.security import clear_auth_cookie, set_auth_cookie


def test_auth_cookie_uses_samesite_none_when_secure() -> None:
    response = Response()
    settings = Settings(
        app_env="production",
        jwt_secret="x" * 48,
        elevenlabs_tool_secret="y" * 48,
        pii_encryption_key="p" * 44,
        elevenlabs_webhook_secret="z" * 48,
        session_cookie_secure=True,
        allowed_origins="https://dashboard.example.com",
    )

    set_auth_cookie(response, "token", settings)

    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "samesite=none" in cookie


def test_clear_auth_cookie_matches_cross_site_attributes() -> None:
    response = Response()
    settings = Settings(
        app_env="production",
        jwt_secret="x" * 48,
        elevenlabs_tool_secret="y" * 48,
        pii_encryption_key="p" * 44,
        elevenlabs_webhook_secret="z" * 48,
        session_cookie_secure=True,
        allowed_origins="https://dashboard.example.com",
    )

    clear_auth_cookie(response, settings)

    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "samesite=none" in cookie
