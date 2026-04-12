from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "daily_review.py"
SPEC = importlib.util.spec_from_file_location("daily_review", SCRIPT_PATH)
assert SPEC and SPEC.loader
daily_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(daily_review)


def test_review_window_uses_restaurant_calendar_day() -> None:
    since, until, label = daily_review.review_window(
        days=1,
        timezone_name="Europe/Zurich",
        target_date=date(2026, 4, 11),
    )

    assert since == datetime(2026, 4, 10, 22, 0, tzinfo=UTC)
    assert until == datetime(2026, 4, 11, 22, 0, tzinfo=UTC)
    assert label == "calendar day 2026-04-11 (Europe/Zurich)"


def test_tool_event_summary_includes_duplicate_context() -> None:
    summary = daily_review.tool_event_summary(
        {
            "tool": "create_booking",
            "result": {
                "success": False,
                "reason": "Risulta già una prenotazione attiva da questo numero nello stesso giorno e orario.",
                "duplicate_booking": {"date": "2026-04-11", "time": "21:00:00"},
            },
        }
    )

    assert "create_booking" in summary
    assert "success=false" in summary
    assert "duplicate=2026-04-11 21:00:00" in summary
