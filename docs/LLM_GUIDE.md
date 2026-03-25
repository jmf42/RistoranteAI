# LLM Guide

This is the primary orientation file for future LLMs working in this repository.

Read this first. Then read:

1. `docs/PRODUCTION_STATE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATABASE.md`
4. `docs/CLOUD_RUN_DEPLOY.md`
5. `docs/SUPABASE_PRODUCTION.md`
6. `docs/DDR_REVIEW.md`

## What The Product Is

Ristorante AI is an AI phone receptionist and restaurant operations dashboard.

The repo covers three practical surfaces:

- voice operations through ElevenLabs and Twilio-facing backend endpoints
- reservation logic and analytics through the FastAPI backend
- owner/operator workflows through the Next.js dashboard

## Current Ground Truth

As of `2026-03-25`:

- backend is deployed on Google Cloud Run
- dashboard is deployed on Google Cloud Run
- database is Supabase Postgres
- live schema is Alembic `0004 (head)`
- the live environment is operational but still staging-grade because it contains demo data and uses default Cloud Run domains

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

## Repo Shape

### Backend

- `backend/app/main.py`
  entrypoint, middleware, readiness, router registration
- `backend/app/api/`
  HTTP boundaries
- `backend/app/services/`
  business logic
- `backend/app/models/entities.py`
  ORM source of truth
- `backend/app/core/`
  config, database, security, observability, rate limiting
- `backend/alembic/`
  migrations
- `backend/tests/`
  backend test suite

### Dashboard

- `dashboard/app/`
  route screens
- `dashboard/components/workspace-provider.tsx`
  current restaurant and session orchestration
- `dashboard/components/login-form.tsx`
  auth entrypoint
- `dashboard/lib/api.ts`
  fetch wrapper with timeouts and cookie credentials

### Operations

- `scripts/production_smoke_test.py`
  repeatable live deployment check
- `scripts/generate_secrets.py`
  local secret bootstrap helper

## Rules Future LLMs Should Preserve

- Keep business rules in backend services, not in the dashboard.
- Keep backend-owned auth.
- Preserve owner/operator role separation.
- Preserve the seeded local demo path unless replacing it with an equally runnable local bootstrap.
- Use Alembic for schema changes.
- Keep ElevenLabs server tools on shared-secret header auth and post-call webhooks on signature verification.
- Treat the current live environment as staging unless the documentation is deliberately updated to say otherwise.

## Deployment Reality That Matters

- frontend API URL is build-time critical for Next.js
- Cloud Run source deploy will use `Dockerfile` if present
- if a Cloud Run service previously used buildpacks, switching to Dockerfile-based source deploys requires `--clear-base-image`
- on Cloud Run default `*.run.app` domains, `/healthz` is intercepted before reaching the app; use `/health` and `/readyz` for public checks

## Verification Standard

Before claiming significant changes are done, run:

```bash
cd backend && uv run ruff check app tests
cd backend && uv run pytest
cd dashboard && npm run build
```

For live deployment claims, also run:

```bash
FRONTEND_URL=https://<frontend-domain> \
BACKEND_URL=https://<backend-domain> \
OWNER_EMAIL=<owner-email> \
OWNER_PASSWORD=<owner-password> \
python3 scripts/production_smoke_test.py
```
