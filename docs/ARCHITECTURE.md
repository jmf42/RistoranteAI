# Architecture

Last updated: `2026-04-10`

## System Shape

The product has three core parts:

- `backend/`
  FastAPI application. Source of truth for auth, restaurant config, booking logic, analytics, and voice orchestration.
- `dashboard/`
  Next.js application for owners and platform operators.
- Supabase Postgres
  Shared application database.

## Live Voice Runtime

```text
Caller
  ↓
Twilio number
  ↓
POST /api/twilio/inbound
  ↓
Backend resolves restaurant + returns TwiML Stream
  ↓
Twilio Media Stream
  ↓
WS /api/twilio/media-stream
  ↓
Backend OpenAI Realtime bridge
  ↙                     ↘
OpenAI Realtime      Backend tools + DB
  ↓                     ↓
Assistant audio      bookings / call logs / analytics
  ↓
Twilio
  ↓
Caller hears the agent
```

## Core Flow

1. The caller dials a Twilio number.
2. Twilio calls `POST /api/twilio/inbound`.
3. The backend finds the restaurant using `restaurants.twilio_phone`.
4. The backend creates a signed stream token and returns TwiML with a Twilio media stream.
5. The Twilio websocket reaches `WS /api/twilio/media-stream`.
6. The backend opens an OpenAI Realtime websocket session.
7. Audio is streamed both directions using `g711_ulaw` (mu-law, 8kHz telephony codec).
8. The model calls backend tools for availability and booking writes.
9. The backend writes authoritative state to Postgres.
10. The dashboard reads the same state the agent used.

## Backend Layers

- `app/api/`
  HTTP and websocket boundaries only.
- `app/services/`
  Booking logic, availability, analytics, and the OpenAI realtime bridge.
- `app/models/entities.py`
  SQLAlchemy source of truth.
- `app/core/`
  config, DB wiring, security helpers, logging, rate limiting.

## Voice Orchestration Boundary

The OpenAI-specific logic lives in:

- `backend/app/services/openai_realtime.py`

It owns:

- prompt generation
- session config generation
- tool schema generation
- Twilio audio bridge
- tool dispatch
- transcript accumulation
- final call persistence
- technical fallback and human transfer orchestration

This keeps business logic private and server-side, which matches the OpenAI Realtime recommendation to keep tool use and orchestration on the application server.

## Dashboard Layers

- `dashboard/app/`
  Route screens.
- `dashboard/components/`
  Shell, layout, workspace UI, shared cards/charts.
- `dashboard/lib/api.ts`
  Browser API wrapper.
- `dashboard/lib/types.ts`
  Shared frontend contracts.

## Operator Studio

The platform operator console is part of the dashboard and exposes:

- live prompt preview
- live session payload preview
- tool schema preview
- real tool sandbox calls
- text-mode Realtime simulation
- multi-scenario simulation suite for lightweight regression checks
- saved per-restaurant runtime config

This is how the prompt/model/voice/VAD/tool behavior is tuned without hard-coding everything in source.

## Database Truth

The database remains authoritative for:

- restaurants
- bookings
- booking events
- customers
- call logs
- users and access control

The voice system is not a separate source of truth. OpenAI Realtime is only the live conversation engine; every real write still goes through the backend and DB.

## Important Production Notes

- `call_logs` are finalized locally from the live session, not fetched later from a vendor console.
- `openai_prompt_override` and `openai_realtime_settings` are stored per restaurant.
- `voice_provider`, `provider_call_id`, and `twilio_call_sid` are the generic call-tracking fields.
- old ElevenLabs columns remain in the schema only as compatibility fields for historical data and migration safety.
- Human transfer is available, but the prompt policy treats it as a last resort. Normal booking clarification should stay with the AI agent unless the caller asks for a human, the request is out of policy, audio remains unclear after targeted retries, or the tool/bridge path cannot safely complete.
