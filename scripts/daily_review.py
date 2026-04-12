#!/usr/bin/env python3
"""
Daily call review script.
Queries the application DB for the last N days of calls, summarizes
outcomes and tool activity, and prints a structured markdown report.

Usage:
    cd backend && uv run python ../scripts/daily_review.py
    cd backend && uv run python ../scripts/daily_review.py --days 3
    cd backend && uv run python ../scripts/daily_review.py --restaurant-slug trattoria-da-mario
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import CallLog, Restaurant


def review_window(
    *,
    days: int,
    timezone_name: str,
    target_date: date | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime | None, str]:
    if target_date is not None:
        tz = ZoneInfo(timezone_name)
        start_local = datetime.combine(target_date, time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return (
            start_local.astimezone(UTC),
            end_local.astimezone(UTC),
            f"calendar day {target_date.isoformat()} ({timezone_name})",
        )

    resolved_now = now or datetime.now(UTC)
    since = resolved_now - timedelta(days=days)
    return since, None, f"last {days} day(s) since {since.strftime('%Y-%m-%d %H:%M')} UTC"


def fetch_calls(db, restaurant_id: str, since: datetime, until: datetime | None = None) -> list[CallLog]:
    stmt = select(CallLog).where(
        CallLog.restaurant_id == restaurant_id,
        CallLog.started_at >= since,
    )
    if until is not None:
        stmt = stmt.where(CallLog.started_at < until)
    return list(db.scalars(stmt.order_by(CallLog.started_at.desc())).all())


def _tool_events(call: CallLog) -> list[dict[str, Any]]:
    extra = call.extra_data or {}
    tool_events = extra.get("tool_events")
    return tool_events if isinstance(tool_events, list) else []


def tool_event_summary(event: dict[str, Any]) -> str:
    tool_name = str(event.get("tool") or "unknown")
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    parts = [tool_name]
    if "success" in result:
        parts.append(f"success={str(bool(result.get('success'))).lower()}")
    if "available" in result:
        parts.append(f"available={str(bool(result.get('available'))).lower()}")
    reason = str(result.get("reason") or "").strip()
    if reason:
        parts.append(reason)
    duplicate = result.get("duplicate_booking") if isinstance(result.get("duplicate_booking"), dict) else None
    if duplicate:
        parts.append(f"duplicate={duplicate.get('date')} {duplicate.get('time')}")
    return " | ".join(parts)


def call_detail(call: CallLog) -> str:
    transcript = (call.transcript_preview or "").replace("\n", " / ").strip()
    transcript_excerpt = transcript[:240] + ("…" if len(transcript) > 240 else "")
    tool_summary = ", ".join(tool_event_summary(event) for event in _tool_events(call)) or "none"
    return (
        f"- {call.started_at.isoformat()} | {call.outcome} | {call.call_status} | {call.summary[:180]}\n"
        f"  transcript: {transcript_excerpt or '<none>'}\n"
        f"  tools: {tool_summary}"
    )


def analyze(calls: list[CallLog], days: int) -> dict[str, Any]:
    total = len(calls)
    if not total:
        return {"total": 0, "days": days}

    durations = [c.duration_seconds for c in calls if c.duration_seconds]
    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    outcome_counts = Counter(c.outcome for c in calls)
    call_status_counts = Counter(c.call_status for c in calls)
    provider_counts = Counter(c.voice_provider for c in calls)
    tool_counts = Counter(
        event.get("tool", "unknown")
        for call in calls
        for event in _tool_events(call)
    )
    technical_failures = [
        c for c in calls if any(event.get("result", {}).get("technical_error") for event in _tool_events(c))
    ]
    zero_calls = [c for c in calls if (c.duration_seconds or 0) == 0]
    long_calls = [c for c in calls if (c.duration_seconds or 0) > 180]
    no_transcript = [c for c in calls if not c.transcript_preview]
    escalated = [c for c in calls if c.outcome == "escalated"]
    tool_errors = [c for c in calls if c.outcome == "tool_error"]

    return {
        "total": total,
        "days": days,
        "avg_duration_seconds": avg_duration,
        "outcome_counts": dict(outcome_counts),
        "call_status_counts": dict(call_status_counts),
        "provider_counts": dict(provider_counts),
        "tool_counts": dict(tool_counts),
        "conversion_rate": round(outcome_counts.get("booking_created", 0) / total * 100, 1),
        "failure_rate": round(call_status_counts.get("failed", 0) / total * 100, 1),
        "technical_failures": technical_failures,
        "zero_calls": zero_calls,
        "long_calls": long_calls,
        "no_transcript": no_transcript,
        "escalated": escalated,
        "tool_errors": tool_errors,
    }


def print_report(
    restaurant: Restaurant,
    stats: dict[str, Any],
    since: datetime,
    *,
    until: datetime | None,
    period_label: str,
    verbose: bool,
) -> None:
    now = datetime.now(UTC)
    total = stats["total"]

    print(f"# Daily Call Review — {restaurant.name}")
    print(f"Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Period: {period_label}")
    if until is not None:
        print(f"Window: {since.strftime('%Y-%m-%d %H:%M')} UTC → {until.strftime('%Y-%m-%d %H:%M')} UTC")
    print()

    if not total:
        print("**No calls in this period.**")
        return

    print("## KPIs")
    print(f"- Total calls: **{total}**")
    print(f"- Booking conversion rate: **{stats['conversion_rate']}%**")
    print(f"- Failed calls: **{stats['failure_rate']}%**")
    print(f"- Avg duration: **{stats['avg_duration_seconds']}s**")
    print(f"- Escalations: **{len(stats['escalated'])}**")
    print()

    print("## Providers")
    for provider, count in sorted(stats["provider_counts"].items(), key=lambda item: (-item[1], item[0])):
        print(f"- {provider}: {count}")
    print()

    print("## Outcomes")
    for outcome, count in sorted(stats["outcome_counts"].items(), key=lambda item: (-item[1], item[0])):
        pct = round(count / total * 100, 1)
        print(f"- {outcome}: {count} ({pct}%)")
    print()

    print("## Call Status")
    for call_status, count in sorted(stats["call_status_counts"].items(), key=lambda item: (-item[1], item[0])):
        pct = round(count / total * 100, 1)
        print(f"- {call_status}: {count} ({pct}%)")
    print()

    if stats["tool_counts"]:
        print("## Tool Usage")
        for tool_name, count in sorted(stats["tool_counts"].items(), key=lambda item: (-item[1], item[0])):
            print(f"- {tool_name}: {count}")
        print()

    flags: list[str] = []
    if stats["failure_rate"] > 20:
        flags.append(f"Failure rate is high ({stats['failure_rate']}%). Check Twilio/OpenAI session logs.")
    if stats["technical_failures"]:
        flags.append(
            f"{len(stats['technical_failures'])} calls had technical tool failures. "
            "Inspect tool payloads and retry paths."
        )
    if stats["long_calls"]:
        flags.append(
            f"{len(stats['long_calls'])} calls lasted over 3 minutes. "
            "Review prompt efficiency and clarifications."
        )
    if stats["zero_calls"]:
        flags.append(f"{len(stats['zero_calls'])} calls have zero duration. Check Twilio routing or immediate hangups.")
    if stats["no_transcript"]:
        flags.append(
            f"{len(stats['no_transcript'])} calls have no transcript preview. "
            "Review realtime transcription events."
        )

    if flags:
        print("## Flags")
        for flag in flags:
            print(f"- {flag}")
        print()

    interesting_calls = (
        stats["technical_failures"] + stats["tool_errors"] + stats["escalated"] + stats["long_calls"]
    )[:5]
    if interesting_calls:
        print("## Calls To Inspect")
        for call in interesting_calls:
            print(call_detail(call))
        print()

    if verbose:
        print("## All Calls")
        for call in stats["calls"]:
            print(call_detail(call))
        print()

    print("---")
    print("*Run `cd backend && uv run python ../scripts/daily_review.py` to regenerate.*")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--restaurant-slug", default="trattoria-madonnina")
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        restaurant = db.scalar(select(Restaurant).where(Restaurant.slug == args.restaurant_slug))
        if not restaurant:
            raise SystemExit(f"Restaurant '{args.restaurant_slug}' not found.")
        since, until, period_label = review_window(
            days=args.days,
            timezone_name=restaurant.timezone or "UTC",
            target_date=args.date,
        )
        calls = fetch_calls(db, restaurant.id, since, until)
        stats = analyze(calls, args.days)
        stats["calls"] = calls
        print_report(
            restaurant,
            stats,
            since,
            until=until,
            period_label=period_label,
            verbose=args.verbose,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
