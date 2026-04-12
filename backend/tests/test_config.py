from __future__ import annotations

import pytest

from app.core import database
from app.core.config import Settings, escape_ini_interpolation


def test_supabase_database_url_uses_psycopg_and_sslmode() -> None:
    settings = Settings(
        database_url="postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
    )
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.database_url


def test_postgres_engine_disables_psycopg_prepared_statements(monkeypatch) -> None:
    monkeypatch.setattr(
        database.settings,
        "database_url",
        "postgresql+psycopg://postgres:secret@aws-0-eu-west-1.pooler.supabase.com:6543/postgres",
    )

    kwargs = database._engine_kwargs()

    assert kwargs["connect_args"]["prepare_threshold"] is None


def test_seed_demo_defaults_off_in_production() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        auto_create_schema=True,
        jwt_secret="production-secret-with-32-bytes-minimum",
        tool_secret="production-tool-secret",
        openai_api_key="sk-test-openai",
        public_base_url="https://api.example.com",
        pii_encryption_key="p" * 44,
        session_cookie_secure=True,
        allowed_origins="https://dashboard.example.com",
    )
    assert settings.seed_demo is False


def test_escape_ini_interpolation_doubles_percent_signs() -> None:
    assert escape_ini_interpolation("postgresql://user:p%40ss@host/db") == "postgresql://user:p%%40ss@host/db"


def test_allowed_origins_accepts_csv_string() -> None:
    settings = Settings(
        _env_file=None,
        allowed_origins="http://127.0.0.1:3001,http://localhost:3001",
    )
    assert settings.allowed_origins == ["http://127.0.0.1:3001", "http://localhost:3001"]


def test_production_requires_explicit_pii_key() -> None:
    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="x" * 48,
            tool_secret="y" * 48,
            openai_api_key="sk-test-openai",
            session_cookie_secure=True,
            allowed_origins="https://dashboard.example.com",
        )


def test_production_rejects_wildcard_origins() -> None:
    with pytest.raises(ValueError, match="cannot contain '\\*'"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="x" * 48,
            tool_secret="y" * 48,
            openai_api_key="sk-test-openai",
            pii_encryption_key="p" * 44,
            session_cookie_secure=True,
            allowed_origins="*",
        )


def test_production_requires_openai_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="x" * 48,
            tool_secret="y" * 48,
            openai_api_key=None,
            pii_encryption_key="p" * 44,
            session_cookie_secure=True,
            allowed_origins="https://dashboard.example.com",
            public_base_url="https://api.example.com",
        )


def test_production_requires_public_base_url() -> None:
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="x" * 48,
            tool_secret="y" * 48,
            openai_api_key="sk-test-openai",
            pii_encryption_key="p" * 44,
            session_cookie_secure=True,
            allowed_origins="https://dashboard.example.com",
        )
