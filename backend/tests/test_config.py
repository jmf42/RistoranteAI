from __future__ import annotations

import pytest

from app.core.config import Settings, escape_ini_interpolation


def test_supabase_database_url_uses_psycopg_and_sslmode() -> None:
    settings = Settings(
        database_url="postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
    )
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.database_url


def test_seed_demo_defaults_off_in_production() -> None:
    settings = Settings(
        app_env="production",
        auto_create_schema=True,
        jwt_secret="production-secret-with-32-bytes-minimum",
        elevenlabs_tool_secret="production-tool-secret",
        pii_encryption_key="p" * 44,
        elevenlabs_webhook_secret="w" * 48,
        session_cookie_secure=True,
        allowed_origins="https://dashboard.example.com",
    )
    assert settings.seed_demo is False


def test_escape_ini_interpolation_doubles_percent_signs() -> None:
    assert escape_ini_interpolation("postgresql://user:p%40ss@host/db") == "postgresql://user:p%%40ss@host/db"


def test_allowed_origins_accepts_csv_string() -> None:
    settings = Settings(allowed_origins="http://127.0.0.1:3001,http://localhost:3001")
    assert settings.allowed_origins == ["http://127.0.0.1:3001", "http://localhost:3001"]


def test_production_requires_explicit_pii_key() -> None:
    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        Settings(
            app_env="production",
            jwt_secret="x" * 48,
            elevenlabs_tool_secret="y" * 48,
            elevenlabs_webhook_secret="z" * 48,
            session_cookie_secure=True,
            allowed_origins="https://dashboard.example.com",
        )


def test_production_rejects_wildcard_origins() -> None:
    with pytest.raises(ValueError, match="cannot contain '\\*'"):
        Settings(
            app_env="production",
            jwt_secret="x" * 48,
            elevenlabs_tool_secret="y" * 48,
            pii_encryption_key="p" * 44,
            elevenlabs_webhook_secret="z" * 48,
            session_cookie_secure=True,
            allowed_origins="*",
        )
