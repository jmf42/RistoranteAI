from __future__ import annotations

import re
from datetime import time
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import AppBaseModel, SyncStatus, VoiceProvider

VALID_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
TIME_RANGE_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _parse_hhmm(value: str) -> time:
    return time.fromisoformat(value)


class RestaurantBase(AppBaseModel):
    slug: str
    name: str
    twilio_phone: str | None = None
    voice_provider: VoiceProvider = VoiceProvider.openai_realtime
    timezone: str = "Europe/Rome"
    address: str
    opening_hours: dict[str, str] = Field(default_factory=dict)
    weekly_closures: list[str] = Field(default_factory=list)
    closure_dates: list[str] = Field(default_factory=list)
    turni: list[dict[str, Any]] = Field(default_factory=list)
    booking_rules: dict[str, Any] = Field(default_factory=dict)
    custom_greeting: str | None = None
    agent_style_notes: str | None = None
    escalation_phone: str | None = None
    is_active: bool = True

    @field_validator("weekly_closures", mode="before")
    @classmethod
    def validate_weekly_closures(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            return value
        normalized = []
        for day in value:
            lowered = day.strip().lower()
            if lowered not in VALID_WEEKDAYS:
                raise ValueError(
                    f"Invalid closure day '{day}'. Must be one of: {', '.join(sorted(VALID_WEEKDAYS))}"
                )
            normalized.append(lowered)
        return normalized

    @field_validator("opening_hours", mode="before")
    @classmethod
    def validate_opening_hours(cls, value: dict[str, str]) -> dict[str, str]:
        if not isinstance(value, dict):
            return value
        for key, time_range in value.items():
            if not TIME_RANGE_RE.match(time_range):
                raise ValueError(
                    f"Invalid opening hours for '{key}': '{time_range}'. Expected format HH:MM-HH:MM"
                )
            start_raw, end_raw = time_range.split("-", maxsplit=1)
            if _parse_hhmm(start_raw) >= _parse_hhmm(end_raw):
                raise ValueError(
                    f"Invalid opening hours for '{key}': start must be earlier than end"
                )
        return value

    @field_validator("turni", mode="before")
    @classmethod
    def validate_turni(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return value
        required_keys = {"name", "start", "end", "max_covers"}
        for i, turno in enumerate(value):
            if not isinstance(turno, dict):
                raise ValueError(f"Turno {i} must be a dict, got {type(turno).__name__}")
            missing = required_keys - turno.keys()
            if missing:
                raise ValueError(f"Turno {i} is missing required keys: {', '.join(sorted(missing))}")
            if not isinstance(turno["name"], str) or not turno["name"].strip():
                raise ValueError(f"Turno {i}: 'name' must be a non-empty string")
            if not TIME_RE.match(str(turno["start"])):
                raise ValueError(f"Turno {i}: 'start' must be HH:MM format, got '{turno['start']}'")
            if not TIME_RE.match(str(turno["end"])):
                raise ValueError(f"Turno {i}: 'end' must be HH:MM format, got '{turno['end']}'")
            if _parse_hhmm(str(turno["start"])) >= _parse_hhmm(str(turno["end"])):
                raise ValueError(f"Turno {i}: 'start' must be earlier than 'end'")
            if not isinstance(turno["max_covers"], int) or turno["max_covers"] < 1:
                raise ValueError(f"Turno {i}: 'max_covers' must be a positive integer")
        return value

    @field_validator("booking_rules", mode="before")
    @classmethod
    def validate_booking_rules(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            return value
        int_keys = {"min_party", "max_party", "large_group_threshold", "max_advance_days", "min_lead_hours"}
        for key in int_keys:
            if key in value:
                if not isinstance(value[key], int) or value[key] < 0:
                    raise ValueError(f"booking_rules.{key} must be a non-negative integer")
        if "min_party" in value and "max_party" in value:
            if value["min_party"] > value["max_party"]:
                raise ValueError("booking_rules.min_party cannot be greater than max_party")
        return value

    @field_validator("closure_dates", mode="before")
    @classmethod
    def validate_closure_dates(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            return value
        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for date_str in value:
            if not iso_re.match(date_str):
                raise ValueError(
                    f"Invalid closure date '{date_str}'. Expected format YYYY-MM-DD"
                )
        return value


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(AppBaseModel):
    slug: str | None = None
    name: str | None = None
    twilio_phone: str | None = None
    voice_provider: VoiceProvider | None = None
    timezone: str | None = None
    address: str | None = None
    opening_hours: dict[str, str] | None = None
    weekly_closures: list[str] | None = None
    closure_dates: list[str] | None = None
    turni: list[dict[str, Any]] | None = None
    booking_rules: dict[str, Any] | None = None
    custom_greeting: str | None = None
    agent_style_notes: str | None = None
    escalation_phone: str | None = None
    is_active: bool | None = None

    @field_validator("weekly_closures", mode="before")
    @classmethod
    def validate_weekly_closures(cls, value: list[str] | None) -> list[str] | None:
        if value is None or not isinstance(value, list):
            return value
        return RestaurantBase.validate_weekly_closures(value)

    @field_validator("opening_hours", mode="before")
    @classmethod
    def validate_opening_hours(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None or not isinstance(value, dict):
            return value
        return RestaurantBase.validate_opening_hours(value)

    @field_validator("turni", mode="before")
    @classmethod
    def validate_turni(cls, value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if value is None or not isinstance(value, list):
            return value
        return RestaurantBase.validate_turni(value)

    @field_validator("booking_rules", mode="before")
    @classmethod
    def validate_booking_rules(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None or not isinstance(value, dict):
            return value
        return RestaurantBase.validate_booking_rules(value)

    @field_validator("closure_dates", mode="before")
    @classmethod
    def validate_closure_dates(cls, value: list[str] | None) -> list[str] | None:
        if value is None or not isinstance(value, list):
            return value
        return RestaurantBase.validate_closure_dates(value)


class RestaurantRead(RestaurantBase):
    id: str
    created_at: str
    updated_at: str
    sync_status: SyncStatus | None = None


class RestaurantSummary(AppBaseModel):
    id: str
    slug: str
    name: str
    twilio_phone: str | None = None
    is_active: bool
    calls_today: int
    bookings_today: int
    booking_rate: float
