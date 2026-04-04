#!/usr/bin/env python3
"""
Daily call review script.
Queries the production DB and ElevenLabs for the last 24h of calls,
analyzes patterns, and prints a structured markdown report to stdout.

Usage:
    cd backend && uv run python ../scripts/daily_review.py
    cd backend && uv run python ../scripts/daily_review.py --days 3
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.integrations.elevenlabs import elevenlabs_service
from app.models import CallLog, Restaurant
from sqlalchemy import select


def fetch_calls(db, restaurant_id: str, since: datetime) -> list[CallLog]:
    return list(
        db.scalars(
            select(CallLog)
            .where(
                CallLog.restaurant_id == restaurant_id,
                CallLog.started_at >= since,
            )
            .order_by(CallLog.started_at.desc())
        ).all()
    )


def fetch_full_transcript(conversation_id: str) -> dict | None:
    return elevenlabs_service.fetch_conversation_transcript(conversation_id)


def elevenlabs_call_status(extra_data: dict) -> str:
    """Extract call_successful from extra_data stored at sync time."""
    meta = extra_data.get("metadata", {}) if extra_data else {}
    analysis = extra_data.get("analysis", {}) if extra_data else {}
    call_successful = meta.get("call_successful") or analysis.get("call_successful")
    if call_successful == "success":
        return "successful"
    if call_successful == "failure":
        return "failed"
    return "unknown"


def elevenlabs_reservation_result(extra_data: dict) -> str:
    analysis = extra_data.get("analysis", {}) if extra_data else {}
    criteria = analysis.get("evaluation_criteria_results", {})
    reservation = criteria.get("reservation_completed", {})
    return reservation.get("result", "unknown")


def analyze(calls: list[CallLog], days: int) -> dict:
    total = len(calls)
    if not total:
        return {"total": 0}

    outcome_counts = Counter(c.outcome for c in calls)
    el_status_counts = Counter(
        elevenlabs_call_status(c.extra_data or {}) for c in calls
    )
    reservation_results = Counter(
        elevenlabs_reservation_result(c.extra_data or {}) for c in calls
    )

    durations = [c.duration_seconds for c in calls if c.duration_seconds]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Calls ElevenLabs marked failed but we have a booking outcome
    outcome_mismatch = [
        c for c in calls
        if elevenlabs_call_status(c.extra_data or {}) == "failed"
        and c.outcome in ("booking_created", "booking_modified", "booking_cancelled")
    ]

    # Long calls (>3 min) — potential confusion/loop
    long_calls = [c for c in calls if (c.duration_seconds or 0) > 180]

    # Zero-duration calls
    zero_calls = [c for c in calls if (c.duration_seconds or 0) == 0]

    # Calls with no transcript preview
    no_transcript = [c for c in calls if not c.transcript_preview]

    # Escalated calls
    escalated = [c for c in calls if c.outcome == "escalated"]

    # info_provided but ElevenLabs says reservation succeeded
    misclassified = [
        c for c in calls
        if c.outcome == "info_provided"
        and elevenlabs_reservation_result(c.extra_data or {}) == "success"
    ]

    return {
        "total": total,
        "days": days,
        "outcome_counts": dict(outcome_counts),
        "el_status_counts": dict(el_status_counts),
        "reservation_results": dict(reservation_results),
        "avg_duration_seconds": round(avg_duration),
        "long_calls": len(long_calls),
        "zero_calls": len(zero_calls),
        "no_transcript": len(no_transcript),
        "escalated": len(escalated),
        "outcome_mismatch": len(outcome_mismatch),
        "misclassified": len(misclassified),
        "conversion_rate": round(
            outcome_counts.get("booking_created", 0) / total * 100, 1
        ),
        "failure_rate": round(
            el_status_counts.get("failed", 0) / total * 100, 1
        ),
        "calls": calls,
        "long_calls_detail": long_calls,
        "escalated_detail": escalated,
        "misclassified_detail": misclassified,
    }


def fetch_problem_transcripts(calls: list[CallLog], max_fetch: int = 5) -> list[dict]:
    """Fetch full transcripts for failed/problematic calls."""
    candidates = [
        c for c in calls
        if elevenlabs_call_status(c.extra_data or {}) == "failed"
        and c.duration_seconds and c.duration_seconds > 30
    ][:max_fetch]

    results = []
    for call in candidates:
        t = fetch_full_transcript(call.elevenlabs_conversation_id)
        if t:
            results.append({
                "conversation_id": call.elevenlabs_conversation_id,
                "started_at": str(call.started_at),
                "duration": call.duration_seconds,
                "outcome": call.outcome,
                "summary": call.summary,
                "transcript": t.get("transcript", ""),
                "analysis": t.get("analysis", {}),
            })
    return results


def print_report(stats: dict, transcripts: list[dict], since: datetime) -> None:
    now = datetime.now(UTC)
    total = stats["total"]

    print(f"# Daily Call Review — {now.strftime('%Y-%m-%d')}")
    print(f"Period: last {stats['days']} day(s) since {since.strftime('%Y-%m-%d %H:%M')} UTC")
    print()

    if not total:
        print("**No calls in this period.**")
        return

    # --- KPIs ---
    print("## KPIs")
    print(f"- Total calls: **{total}**")
    print(f"- Booking conversion rate: **{stats['conversion_rate']}%**")
    print(f"- ElevenLabs failure rate: **{stats['failure_rate']}%**")
    print(f"- Avg duration: **{stats['avg_duration_seconds']}s** ({round(stats['avg_duration_seconds']/60, 1)} min)")
    print(f"- Escalations: **{stats['escalated']}**")
    print()

    # --- Outcomes ---
    print("## Outcome Distribution")
    for outcome, count in sorted(stats["outcome_counts"].items(), key=lambda x: -x[1]):
        pct = round(count / total * 100, 1)
        print(f"- {outcome}: {count} ({pct}%)")
    print()

    # --- ElevenLabs status ---
    print("## ElevenLabs Call Status")
    for status, count in sorted(stats["el_status_counts"].items(), key=lambda x: -x[1]):
        pct = round(count / total * 100, 1)
        print(f"- {status}: {count} ({pct}%)")
    print()

    # --- Flags ---
    flags = []
    if stats["failure_rate"] > 40:
        flags.append(f"HIGH failure rate ({stats['failure_rate']}%) — check tool connectivity and secrets")
    if stats["long_calls"] > 0:
        flags.append(f"{stats['long_calls']} calls over 3 min — possible agent loops or confusion")
    if stats["zero_calls"] > 0:
        flags.append(f"{stats['zero_calls']} zero-duration calls — connection or Twilio routing issues")
    if stats["escalated"] > 0:
        flags.append(f"{stats['escalated']} escalations — review if triggers were appropriate")
    if stats["misclassified"] > 0:
        flags.append(f"{stats['misclassified']} calls where ElevenLabs says booking succeeded but DB shows info_provided — outcome detection gap")
    if stats["outcome_mismatch"] > 0:
        flags.append(f"{stats['outcome_mismatch']} calls where ElevenLabs says failed but booking exists — possible double-entry or sync lag")

    if flags:
        print("## Flags")
        for f in flags:
            print(f"- ⚠️  {f}")
        print()

    # --- Transcripts of failed calls ---
    if transcripts:
        print("## Failed Call Transcripts")
        for t in transcripts:
            print(f"\n### {t['started_at'][:16]} UTC — {t['duration']}s — {t['outcome']}")
            print(f"**Summary:** {t['summary']}")
            criteria = t["analysis"].get("evaluation_criteria_results", {})
            for k, v in criteria.items():
                print(f"**{k}:** {v.get('result')} — {(v.get('rationale') or '')[:120]}")
            print()
            print("**Transcript:**")
            print("```")
            print((t["transcript"] or "")[:1500])
            print("```")
    print()
    print("---")
    print("*Run `cd backend && uv run python ../scripts/daily_review.py` to regenerate.*")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()

    since = datetime.now(UTC) - timedelta(days=args.days)

    db = SessionLocal()
    try:
        restaurant = db.scalar(select(Restaurant).where(Restaurant.slug == "trattoria-madonnina"))
        if not restaurant:
            print("ERROR: restaurant not found", file=sys.stderr)
            sys.exit(1)

        calls = fetch_calls(db, restaurant.id, since)
        stats = analyze(calls, args.days)
        transcripts = fetch_problem_transcripts(calls)
        print_report(stats, transcripts, since)
    finally:
        db.close()


if __name__ == "__main__":
    main()
