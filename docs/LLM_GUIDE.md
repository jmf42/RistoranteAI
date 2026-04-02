# LLM Guide

This is the primary orientation file for future LLMs working in this repository.

Read this first. Then read:

1. `docs/PRODUCTION_STATE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATABASE.md`
4. `docs/OPERATIONS.md`
5. `docs/INTEGRATIONS.md`

## What The Product Is

Ristorante AI is an AI phone receptionist and restaurant operations dashboard.

The repo covers three practical surfaces:

- voice operations through ElevenLabs and Twilio-facing backend endpoints
- reservation logic and analytics through the FastAPI backend
- owner/operator workflows through the Next.js dashboard

## Current Ground Truth

As of `2026-03-28`:

- backend is deployed on Google Cloud Run (`ristorante-ai-api`, revision `00016-787`)
- dashboard is deployed on Google Cloud Run (`ristorante-ai-dashboard`, revision `00006-zh7`)
- database is Supabase Postgres
- live schema version: `0005 (head)` — migrations `0006`, `0007`, and `0008` exist locally but have NOT been deployed
- the live environment is operational but staging-grade (demo data, default Cloud Run domains)
- the Twilio inbound path is backend-owned at `POST /api/twilio/inbound`
- the Twilio fallback path is `POST /api/twilio/voice-fallback`
- the old manual Twilio target `https://api.elevenlabs.io/v1/convai/twilio/inbound_call` is a dead path — do not reuse it
- the post-call webhook in ElevenLabs was **auto-disabled** due to 401 errors — must be re-enabled after fixing the signing secret
- the AI agent is named **Edoardo** (responds to this name only if asked)
- the restaurant in the live demo is **Trattoria Madonnina** (UUID: `a1f59bc4-b750-4f2c-bcb1-0a703ac732c7`)
- owner login: `owner@trattoriamadonnina.it` (name: Giovanni Mercadante)

Do not describe the current environment as final production unless `docs/PRODUCTION_STATE.md` says that is true.

## What Changed Recently

The current codebase already includes:

- Alembic migrations for production schema control
- request ID middleware and JSON logging
- rate limiting
- Cloud Run-ready deployment packaging
- secure cross-origin session cookies
- bookings export and calls export
- booking events history endpoint and dashboard history view
- production smoke testing
- server-side Twilio inbound call registration with ElevenLabs `register_call`
- `call_status` field on `CallLog` (successful/failed/unknown) — migration `0006`, NOT YET deployed
- raw webhook inbox table (`raw_webhook_events`) — migration `0007`, NOT YET deployed
- Supabase RLS hardening on all public app tables — migration `0008`, NOT YET deployed
- `tool_error` as a new `CallOutcome` enum value — NOT YET deployed
- `{saluto}` placeholder support in `custom_greeting` (resolves to Buongiorno/Buonasera by hour) — NOT YET deployed
- `current_date`, `current_time`, `current_day_of_week` added to personalization dynamic variables — NOT YET deployed
- debug logging on 401 failures in `deps.py`
- `GET /tools/health` diagnostic endpoint

## Pending Deploy Items

These are implemented in code but NOT yet deployed to Cloud Run:

1. Migrations `0006` through `0008` — `call_status`, `raw_webhook_events`, and Supabase RLS hardening
2. `{saluto}` greeting fix in `personalization.py`
3. `tool_error` outcome detection in `webhooks.py`
4. `call_status` in webhook, schema, dashboard
5. Tool health endpoint
6. Debug logging on auth failures

**Deploy order:** run `alembic upgrade head` on production DB first, then deploy backend.

## Known Issues (Do Not Regress)

### Security

- Twilio inbound endpoint (`/api/twilio/inbound`) has NO signature validation — spoofable
- Post-call webhook signature verification is guarded by `if settings.elevenlabs_webhook_secret` — should be mandatory
- Tool secret is a plain string with no rotation mechanism
- Operator role not scoped to specific restaurants (can access any)
- No login attempt tracking / brute-force protection

### Data

- Confirmation codes are sequential and predictable (`TM-032801`, `TM-032802`) — enumerable
- Confirmation code generation has only 1 collision retry — race condition under concurrent load
- Heatmap analytics use UTC timestamps instead of restaurant local timezone
- `ElevenLabs` API errors are silently swallowed — dashboard shows stale call data with no warning

### UX / Dashboard

- No pagination on Calls or Bookings pages — loads all records at once
- Heatmap requires `min-w-[640px]` — broken on mobile
- `window.confirm()` used for destructive actions (cancel, delete)
- Call sync (`sync_recent_calls_from_elevenlabs`) fires on every GET `/calls` — slow and fragile
- No per-section error boundaries — one API failure crashes entire page
- No optimistic updates on status toggles

### ElevenLabs Agent Behavior

- Agent was reading confirmation codes aloud — fixed in system prompt
- Agent was asking for phone number — fixed (use `{{caller_phone}}` dynamic variable)
- Agent was not ending call after goodbye — fixed with CHIUSURA section
- Agent was saying the full year ("duemilaventisei") — fixed with "Mai dire l'anno nelle date"
- Agent was asking about allergies/notes proactively — fixed with DIVIETI section

## Repo Shape

### Backend

- `backend/app/main.py` — entrypoint, middleware, readiness, router registration
- `backend/app/api/` — HTTP boundaries
- `backend/app/services/` — business logic
- `backend/app/models/entities.py` — ORM source of truth
- `backend/app/core/` — config, database, security, observability, rate limiting
- `backend/alembic/` — migrations
- `backend/tests/` — backend test suite (95 tests)

### Dashboard

- `dashboard/app/` — route screens
- `dashboard/components/workspace-provider.tsx` — current restaurant and session orchestration
- `dashboard/components/login-form.tsx` — auth entrypoint
- `dashboard/lib/api.ts` — fetch wrapper with timeouts and cookie credentials
- `dashboard/lib/types.ts` — TypeScript contracts mirroring backend payload shapes

### Operations

- `scripts/production_smoke_test.py` — repeatable live deployment check
- `scripts/generate_secrets.py` — local secret bootstrap helper

## Rules Future LLMs Should Preserve

- Keep business rules in backend services, not in the dashboard.
- Keep backend-owned auth.
- Preserve owner/operator role separation.
- Preserve the seeded local demo path unless replacing it with an equally runnable local bootstrap.
- Use Alembic for schema changes — never `AUTO_CREATE_SCHEMA=true` in production.
- Keep ElevenLabs server tools on shared-secret header auth and post-call webhooks on signature verification.
- Keep Twilio inbound voice routing on `POST /api/twilio/inbound` — not the dead legacy ElevenLabs URL.
- Keep Twilio emergency fallback on `POST /api/twilio/voice-fallback`.
- Treat the current live environment as staging unless documentation is deliberately updated.
- Never break the 95 passing tests.

## Deployment Reality That Matters

- frontend API URL (`NEXT_PUBLIC_API_BASE_URL`) is build-time critical for Next.js — wrong at build = bad target shipped
- Cloud Run source deploy uses `Dockerfile` if present in source directory
- if a Cloud Run service previously used buildpacks, switching requires `--clear-base-image`
- on Cloud Run default `*.run.app` domains, `/healthz` is intercepted before reaching the app — use `/health` and `/readyz`
- there has already been schema/API drift in this workspace around restaurant AI settings — before changing those fields, verify the live Alembic version, latest migration file, and current ORM model together
- `PII_ENCRYPTION_KEY` must stay stable — changing it makes historical encrypted data unreadable

## Verification Standard

Before claiming significant changes are done, run:

```bash
cd backend && uv run ruff check app tests
cd backend && uv run pytest
cd dashboard && npm run build
```

For live deployment claims, also run:

```bash
FRONTEND_URL=https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app \
BACKEND_URL=https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app \
OWNER_EMAIL=owner@trattoriamadonnina.it \
OWNER_PASSWORD=<password> \
python3 scripts/production_smoke_test.py
```
