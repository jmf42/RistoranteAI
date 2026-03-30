# Production State

This file is a date-stamped snapshot of the currently deployed environment.

## Snapshot Date

`2026-03-28`

## Current Deployment

Google Cloud:

- project: `ristorante-ai-20260324-9471`
- region: `europe-west1`

Cloud Run services:

- backend service: `ristorante-ai-api`
- backend latest ready revision: `ristorante-ai-api-00016-787`
- backend URL: `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app`
- frontend service: `ristorante-ai-dashboard`
- frontend latest ready revision: `ristorante-ai-dashboard-00006-zh7`
- frontend URL: `https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app`

## Current Database

Provider:

- Supabase Postgres

Operational status:

- reachable through the Supabase pooler
- live schema version: `0005 (head)`
- migration `0006` exists locally but has NOT been applied to production

Current live/staging table counts at verification time:

- `restaurants: 1`
- `users: 2`
- `user_restaurants: 1`
- `bookings: 5+` (growing from test calls)
- `customers: 3+`
- `booking_events: 3+`
- `call_logs: 5+` (growing from test calls)

## Live Restaurant

- name: **Trattoria Madonnina**
- UUID: `a1f59bc4-b750-4f2c-bcb1-0a703ac732c7`
- slug: `madonnina`
- timezone: `Europe/Rome`
- city: Milan
- Twilio phone: configured
- ElevenLabs agent: configured and active

## Current User Accounts

- owner: `owner@trattoriamadonnina.it` — Giovanni Mercadante (role: owner)
- operator: `operator@ristorante.ai` (role: operator)

## ElevenLabs Integration Status

- agent: active, receiving calls
- voice model: Flash v2.5 (recommended to upgrade to v3 Conversational)
- post-call webhook: **AUTO-DISABLED** — ElevenLabs disabled it due to repeated 401 errors
  - root cause: `ELEVENLABS_WEBHOOK_SECRET` in GCP Secret Manager does not match the signing key ElevenLabs uses
  - fix: update the secret in GCP Secret Manager, redeploy backend, re-enable webhook in ElevenLabs agent settings
- tool endpoints: working after fixing `ELEVENLABS_TOOL_SECRET` header value
- ElevenLabs quota: check usage dashboard — at least one call failed with "quota limit exceeded"

## Pending Backend Changes (Implemented, NOT Deployed)

These are committed locally but not yet live on Cloud Run:

1. **Migration 0006** — `call_status` column on `call_logs` (successful/failed/unknown)
2. **`{saluto}` greeting** — `personalization.py` resolves `{saluto}` placeholder before sending to ElevenLabs
3. **`tool_error` outcome** — webhook detects tool errors and sets outcome accordingly
4. **`call_status` in dashboard** — red/green/gray dot indicator on calls page
5. **Tool health endpoint** — `GET /tools/health` for auth verification
6. **Debug logging** — 401 failures log prefix hints

Deploy checklist:
```bash
# 1. Apply migration
DATABASE_URL='<supabase-pooler-url>' uv run alembic upgrade head
# 2. Deploy backend
gcloud run deploy ristorante-ai-api --project ristorante-ai-20260324-9471 --region europe-west1 --source backend --clear-base-image --allow-unauthenticated
```

## What Was Verified Live

- backend health endpoint
- backend readiness endpoint
- backend owner login
- authenticated analytics request
- authenticated bookings request
- authenticated calls request
- authenticated bookings export
- authenticated calls export
- booking events history endpoint
- cross-origin session cookie behavior
- browser-origin login/session flow from deployed frontend
- frontend dashboard root rendering after authentication
- repeatable smoke test in `scripts/production_smoke_test.py`
- Twilio-style POST to `POST /api/twilio/inbound`
- valid ElevenLabs `<Connect><Stream .../></Connect>` TwiML from backend inbound route
- backend binding of `ELEVENLABS_API_KEY` from Google Secret Manager
- successful end-to-end calls with booking creation and modification

## What Is Live But Not Final-Production

The current environment is best described as a live staging deployment, not the final public production system.

Reasons:

- Supabase still contains demo/staging data
- default Cloud Run domains are still in use
- custom domains are not configured
- real PSTN verification needed after Twilio console changes
- telephony behavior still depends on Twilio console routing staying pointed at backend inbound route
- post-call webhook currently disabled (must be re-enabled)

## Current Runtime Secrets Model

Secrets are stored in Google Secret Manager.

Current secret names:

- `database-url`
- `jwt-secret`
- `pii-encryption-key`
- `elevenlabs-tool-secret`
- `elevenlabs-personalization-secret`
- `elevenlabs-webhook-secret` ← **must match ElevenLabs agent signing key to re-enable webhook**
- `elevenlabs-api-key`

## Current Auth Reality

- backend-owned auth
- session cookie-based auth
- production cookie uses `Secure` + `SameSite=None`
- dashboard uses `credentials: "include"`

## Important Operational Gotchas Already Learned

These have already broken once and should not be forgotten:

1. The frontend must receive `NEXT_PUBLIC_API_BASE_URL` at build time, not only runtime.
2. Cloud Run source deploy will use `Dockerfile` if one exists in the source directory.
3. If a service previously used buildpacks, switching to Dockerfile-based source deploys requires `--clear-base-image`.
4. On default Cloud Run `*.run.app` domains, `/healthz` is intercepted before the request reaches the service. Use `/health` and `/readyz`.
5. Historical data needed backfill once `customers` and `booking_events` were introduced.
6. `ALLOWED_ORIGINS` must match the actual deployed frontend origin.
7. Do not point Twilio to `https://api.elevenlabs.io/v1/convai/twilio/inbound_call` — returns 404.
8. The supported live voice path is Twilio → backend `POST /api/twilio/inbound` → ElevenLabs `register_call`.
9. ElevenLabs tool secrets must match exactly between ElevenLabs tool config and GCP Secret Manager. Mismatch causes 401 on every tool call.
10. ElevenLabs will auto-disable webhooks after repeated 401 errors. Re-enable from agent settings after fixing the secret.
11. ElevenLabs has per-plan call minute quotas. Calls will fail with "quota limit exceeded" when exceeded.

## What Must Happen Before Calling This True Production

1. Fix and re-enable the post-call webhook
2. Apply migration 0006
3. Deploy pending backend changes
4. Create a clean production Supabase project (separate from staging)
5. Run Alembic migrations there
6. Bootstrap only real tenant data
7. Add custom domains
8. Wire real Twilio credentials/config
9. Wire real ElevenLabs credentials/config
10. Verify real PSTN inbound call flow end to end

## Recommended Language For Future Docs Or Stakeholders

Safe phrasing:

- "live staging deployment"
- "production-shaped deployment"
- "Cloud Run + Supabase environment is operational"

Unsafe phrasing unless the remaining steps are done:

- "final production"
- "customer-ready production database"
- "fully launched telephony production system"
