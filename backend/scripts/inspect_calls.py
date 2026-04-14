"""Quick inspection script: fetch last N call logs with transcripts and tool events."""
from __future__ import annotations

import json
import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.lkevvvbyugzsrlggfcjn:Loco13Abreu%4042@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require",
)

# Normalize driver
db_url = DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(db_url)

LIMIT = 10

with Session(engine) as db:
    # Also fetch the restaurant config for turni context
    rest_row = db.execute(text("SELECT id, name, turni, opening_hours, weekly_closures, closure_dates, booking_rules FROM restaurants LIMIT 1")).first()
    if rest_row:
        print("=" * 80)
        print("RESTAURANT CONFIG")
        print("=" * 80)
        print(f"  ID:               {rest_row[0]}")
        print(f"  Name:             {rest_row[1]}")
        print(f"  Turni:            {json.dumps(rest_row[2], indent=2, ensure_ascii=False)}")
        print(f"  Opening Hours:    {json.dumps(rest_row[3], indent=2, ensure_ascii=False)}")
        print(f"  Weekly Closures:  {json.dumps(rest_row[4], ensure_ascii=False)}")
        print(f"  Closure Dates:    {json.dumps(rest_row[5], ensure_ascii=False)}")
        print(f"  Booking Rules:    {json.dumps(rest_row[6], indent=2, ensure_ascii=False)}")
        print()

    rows = db.execute(
        text(
            """
            SELECT
                id,
                started_at,
                duration_seconds,
                outcome,
                call_status,
                summary,
                transcript_preview,
                extra_data,
                twilio_call_sid,
                booking_id
            FROM call_logs
            ORDER BY started_at DESC
            LIMIT :limit
            """
        ),
        {"limit": LIMIT},
    ).all()

    print("=" * 80)
    print(f"LAST {LIMIT} CALLS (newest first)")
    print("=" * 80)
    for i, row in enumerate(rows):
        call_id, started_at, duration, outcome, call_status, summary, transcript, extra_data, twilio_sid, booking_id = row
        extra = extra_data if isinstance(extra_data, dict) else {}
        tool_events = extra.get("tool_events", [])

        print(f"\n{'─' * 80}")
        print(f"CALL #{i+1}")
        print(f"  ID:            {call_id}")
        print(f"  Twilio SID:    {twilio_sid}")
        print(f"  Started:       {started_at}")
        print(f"  Duration:      {duration}s")
        print(f"  Outcome:       {outcome}")
        print(f"  Call Status:   {call_status}")
        print(f"  Booking ID:    {booking_id}")
        print(f"  Summary:       {summary}")
        print()

        # Tool events
        if tool_events:
            print(f"  TOOL EVENTS ({len(tool_events)}):")
            for te in tool_events:
                tool_name = te.get("tool", "?")
                args = te.get("arguments", {})
                result = te.get("result", {})
                print(f"    ► {tool_name}")
                print(f"      Args:   {json.dumps(args, ensure_ascii=False)}")
                # For check_availability, show the full result
                if tool_name == "check_availability":
                    print(f"      Result: {json.dumps(result, indent=8, ensure_ascii=False)}")
                else:
                    # Compact for others
                    compact_result = {k: v for k, v in result.items() if k in ("success", "available", "open", "found", "reason", "duplicate_booking", "technical_error", "should_escalate")}
                    print(f"      Result: {json.dumps(compact_result, ensure_ascii=False)}")
            print()

        # Full transcript
        print(f"  TRANSCRIPT:")
        if transcript:
            for line in transcript.split("\n"):
                print(f"    {line}")
        else:
            print(f"    (no transcript)")
        print()

engine.dispose()
