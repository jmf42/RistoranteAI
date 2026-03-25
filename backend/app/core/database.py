from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    kwargs: dict = {"future": True}
    if settings.database_url.startswith("sqlite"):
        database_path = settings.database_url.split("///", maxsplit=1)[-1]
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = settings.db_pool_recycle_seconds
        kwargs["pool_timeout"] = settings.db_pool_timeout_seconds
        kwargs["pool_use_lifo"] = True
    return kwargs


engine = create_engine(settings.database_url, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "restaurants" not in table_names:
        return

    restaurant_columns = {column["name"] for column in inspector.get_columns("restaurants")}
    if "assistant_settings" in restaurant_columns:
        return

    default_expr = "'{}'" if engine.dialect.name == "sqlite" else "'{}'::json"
    statement = (
        "ALTER TABLE restaurants "
        f"ADD COLUMN assistant_settings JSON NOT NULL DEFAULT {default_expr}"
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(statement)


def init_db() -> None:
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
