# Production State

This file is a date-stamped snapshot of the currently deployed environment.

## Snapshot Date

`2026-03-25`

## Current Deployment

Google Cloud:

- project: `ristorante-ai-20260324-9471`
- region: `europe-west1`

Cloud Run services:

- backend service: `ristorante-ai-api`
- backend latest ready revision: `ristorante-ai-api-00005-vhx`
- backend URL: `https://ristorante-ai-api-534989834839.europe-west1.run.app`
- frontend service: `ristorante-ai-dashboard`
- frontend latest ready revision: `ristorante-ai-dashboard-00003-xmq`
- frontend URL: `https://ristorante-ai-dashboard-534989834839.europe-west1.run.app`

## Current Database

Provider:

- Supabase Postgres

Operational status:

- reachable through the Supabase pooler
- schema version verified at `0004 (head)`

Current live/staging table counts at verification time:

- `restaurants: 1`
- `users: 2`
- `user_restaurants: 1`
- `bookings: 3`
- `customers: 3`
- `booking_events: 3`
- `call_logs: 3`

These numbers are not contractual product behavior. They are simply the state of the current staged dataset at the time of documentation.

## What Was Verified Live

Verified during the deployment and follow-up checks:

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
- browser-origin login/session flow from the deployed frontend origin
- frontend dashboard root rendering after authentication
- repeatable smoke test in `scripts/production_smoke_test.py`

## What Is Live But Not Final-Production

The current environment is best described as a live staging deployment, not the final public production system.

Reasons:

- Supabase still contains demo/staging data
- default Cloud Run domains are still in use
- custom domains are not configured
- Twilio and ElevenLabs production credentials are not part of this verified state
- telephony end-to-end live call flow is not verified here

## Current Runtime Secrets Model

Secrets are stored in Google Secret Manager.

Current secret names:

- `database-url`
- `jwt-secret`
- `pii-encryption-key`
- `elevenlabs-tool-secret`
- `elevenlabs-personalization-secret`
- `elevenlabs-webhook-secret`

## Current Auth Reality

- backend-owned auth
- session cookie-based auth
- production cookie uses:
  - `Secure`
  - `SameSite=None`
- dashboard uses `credentials: "include"`

## Important Operational Gotchas Already Learned

These have already broken once and should not be forgotten:

1. The frontend must receive `NEXT_PUBLIC_API_BASE_URL` at build time, not only runtime.
2. Cloud Run source deploy will use `Dockerfile` if one exists in the source directory.
3. If a service previously used buildpacks, switching to Dockerfile-based source deploys requires `--clear-base-image`.
4. On default Cloud Run `*.run.app` domains, `/healthz` is intercepted before the request reaches the service. Use `/health` and `/readyz` for public checks.
5. Historical data needed backfill once `customers` and `booking_events` were introduced.
6. `ALLOWED_ORIGINS` must match the actual deployed frontend origin.

## What Must Happen Before Calling This True Production

1. create a clean production Supabase project
2. run Alembic migrations there
3. bootstrap only real tenant data
4. add custom domains
5. wire real Twilio credentials/config
6. wire real ElevenLabs credentials/config
7. verify live inbound call flow end to end

## Recommended Language For Future Docs Or Stakeholders

Safe phrasing:

- “live staging deployment”
- “production-shaped deployment”
- “Cloud Run + Supabase environment is operational”

Unsafe phrasing unless the remaining steps are done:

- “final production”
- “customer-ready production database”
- “fully launched telephony production system”
