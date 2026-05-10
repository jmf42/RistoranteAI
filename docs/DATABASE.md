# Database

Last updated: `2026-05-10`

This document describes the current database shape relevant to the phone agent.

## Source of Truth

Supabase Postgres is the source of truth for:

- restaurants
- users
- bookings
- booking events
- customers
- call logs
- guest booking tokens
- notification outbox entries

The voice model never becomes the source of truth for reservations.

## Voice-Relevant Tables

### `restaurants`

Important fields:

- `twilio_phone`
- `voice_provider`
- `timezone`
- `opening_hours`
- `weekly_closures`
- `closure_dates`
- `turni`
- `booking_rules`
- `custom_greeting`
- `agent_style_notes`
- `escalation_phone`
- `openai_prompt_override`
- `openai_realtime_settings`
- `online_booking_settings`

Compatibility-only legacy field still present:

- `elevenlabs_agent_id`

### `call_logs`

Important fields:

- `voice_provider`
- `provider_call_id`
- `twilio_call_sid`
- `started_at`
- `duration_seconds`
- `outcome`
- `call_status`
- `booking_id`
- `summary`
- `transcript_preview`
- `extra_data`

Compatibility-only legacy field still present:

- `elevenlabs_conversation_id`

`extra_data` is where the realtime bridge stores:

- `openai_session_id`
- `tool_events`
- `response_usage`
- `transcription_events`
- `dropped_input_audio_packets`
- call error metadata, when finalization captures an error path
- basic call metadata

## Booking Write Path

Phone-agent, dashboard, and public web reservation writes all go through the same booking tables and services.

- new booking → `bookings`
- modify booking → `bookings` + `booking_events`
- cancel booking → `bookings` + `booking_events`

The voice runtime and public reservation runtime do not bypass the booking engine.

Public web reservations add:

- guest email storage on `bookings` and `customers`
- `booking_guest_tokens` for temporary manage links
- `notification_outbox` for queued email notifications
- `channel_metadata` and `idempotency_key` on bookings for safer web submissions

## Config Freshness Note

Restaurant config used on the hot tool path is cached briefly in memory for performance. Restaurant updates and studio config saves now invalidate that cache immediately, so prompt and booking-rule changes take effect on the next tool call instead of waiting for TTL expiry.

## Migrations Relevant To The Realtime Migration

- `20260404_0010_openai_realtime_voice_runtime.py`
  generic voice-provider fields for the new runtime
- `20260405_0011_persist_openai_agent_config.py`
  per-restaurant prompt/session config persistence
- `20260419_0012_public_online_reservations.py`
  public reservation settings, guest manage links, email fields, and notification outbox

## Production Rule

Do not change schema manually in Supabase.

Use:

```bash
cd backend
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```
