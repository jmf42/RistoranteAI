# Production State

Last updated: `2026-04-10`

This file is the deployment-state snapshot for the OpenAI Realtime live-staging rollout.

## Snapshot Date

`2026-04-10`

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

Important deployment caveat:

- local fixes made after the `2026-04-10` call review are not live until the backend is redeployed
- the live `ALLOWED_ORIGINS` setting should include the current dashboard URL above before relying on browser-origin smoke tests

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

## Verified Locally

- backend lint
- backend tests
- dashboard production build
- Alembic upgrade to `head` on a fresh local database

Baseline verification commands:

- `cd backend && uv run ruff check app tests`
- `cd backend && uv run pytest`
- `cd dashboard && npm run build`

## Verified Live On `2026-04-10`

- Cloud Run backend received Twilio inbound webhooks and media streams.
- OpenAI Realtime sessions ran against real phone calls.
- Two real reservation calls completed successfully and persisted bookings.
- Call transcripts, tool events, and usage metadata persisted to Supabase.
- Twilio billing records and OpenAI usage metadata were reviewed for the day.

## Known Live Issues From `2026-04-10` Review

- One unclear-audio call escalated after the agent treated garbled fragments too confidently.
- A Postgres prepared-statement collision interrupted call finalization through the Supabase pooler.
- One successful call shortened the caller name `Juan Manuel` to `Manuel`.
- Live CORS config allowed an older dashboard origin but not the current visible dashboard URL.

Local code/docs now address the first three items. The CORS item is an environment/deploy configuration task.

## Still Needing Live Re-Verification After Deploy

- prepared-statement fix under a real Supabase pooled connection
- prompt behavior on unclear audio and full customer names
- human transfer with real Twilio credentials and `escalation_phone`
- browser access from the current dashboard URL after `ALLOWED_ORIGINS` is corrected

## Before Calling This Production-Ready

1. redeploy backend after the `2026-04-10` reliability fixes
2. align `ALLOWED_ORIGINS` with the current dashboard URL
3. confirm `/studio` saves and reloads live config correctly
4. test one real inbound Twilio call end to end after redeploy
5. test human transfer only for the allowed escalation cases
6. verify calls, transcripts, bookings, tool events, and usage persist correctly
7. decide whether to clean the existing staging Supabase project or create a separate production project

Until those are done, this is a live-staging system with real OpenAI/Twilio traffic, not a verified public-production rollout.
