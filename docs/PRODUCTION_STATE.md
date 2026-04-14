# Production State

Last updated: `2026-04-14`

This file is the deployment-state snapshot for the OpenAI Realtime live-staging rollout.

## Snapshot Date

`2026-04-14`

## Current Code Reality

The repository now targets:

- Twilio as telephony ingress
- OpenAI Realtime as the live voice engine
- backend-owned tool execution
- local call finalization in `call_logs`
- operator-managed prompt and session tuning through `/studio`

The old ElevenLabs runtime path has been removed from the active app code.

## Current Deployment Reality

The public staging environment is deployed on Cloud Run and is already using the backend-owned Twilio + OpenAI Realtime call path.

Current public endpoints:

- backend: `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app`
- dashboard: `https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app`

Current observed live revisions on `2026-04-10`:

- backend: `ristorante-ai-api-00054-26n`
- dashboard: `ristorante-ai-dashboard-00032-k99`

Treat this as `live staging`, not final public production.

- local fixes made on `2026-04-14` (realtime confirmation, booking linkage) require a backend redeploy to take effect.
- the live `ALLOWED_ORIGINS` setting must match the current dashboard URL.

## Current Database Reality

The repository schema includes:

- generic call tracking fields from migration `0010`
- persistent per-restaurant OpenAI config from migration `0011`

Key live-agent fields:

- `restaurants.openai_prompt_override`
- `restaurants.openai_realtime_settings`
- `call_logs.voice_provider`
- `call_logs.provider_call_id`
- `call_logs.twilio_call_sid`

Legacy compatibility columns still exist in the schema for historical safety:

- `restaurants.elevenlabs_agent_id`
- `call_logs.elevenlabs_conversation_id`

They are no longer part of the active voice runtime.

## Verified Locally (2026-04-14)

- backend lint: Clean (ruff)
- backend tests: 165/165 Passed
- dashboard production build: Passing
- Alembic upgrade to `head` (0011): Verified

Baseline verification commands (via Makefile):

- `make verify-backend`
- `make verify-dashboard`

## Verified Live On `2026-04-10` (Snapshot)

- Cloud Run backend received Twilio inbound webhooks and media streams.
- OpenAI Realtime sessions ran against real phone calls.
- Two real reservation calls completed successfully and persisted bookings.

## Recent Fixes (2026-04-14)

The following reliability items were addressed and verified locally:

- **Realtime Confirmation**: Simplified the confirmation flow to be more robust against model interruptions and confidence issues.
- **Multilingual Stability**: Fixed language-switching and confirmation handling for non-Italian agents.
- **Booking Linkage**: Resolved a race condition where `booking_id` was not correctly linked in `call_logs`.
- **Prepared Statements**: Optimized Postgres connection handling to avoid statement collisions through the Supabase pooler.

## Known Live Issues (Post-April 14 Deploy)

- *Pending validation of the above fixes under real phone traffic.*

## Before Calling This Production-Ready

1. confirm `/studio` saves and reloads live config correctly after the latest push.
2. test one real inbound Twilio call end to end after redeploy.
3. test human transfer only for the allowed escalation cases.
4. verify calls, transcripts, bookings, tool events, and usage persist correctly.
