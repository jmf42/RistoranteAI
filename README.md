# Ristorante AI

Last updated: `2026-05-23`

Ristorante AI is an AI phone receptionist and restaurant operations dashboard for restaurants.

The repo proves one connected operating loop:

- callers reach the restaurant through Twilio
- the backend bridges the call to OpenAI Realtime
- booking tools run on the backend against real capacity rules
- owners/operators use the dashboard against the same database
- guests can create and manage public web reservations

## Current State

This is a live-staging project, not final public production. It is deployed and ready for controlled production testing.

Cloud Run services:

- backend: `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app`
- dashboard: `https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app`

Database:

- runtime: Supabase Postgres
- repo migration target: Alembic `0012 (head)`
- current readiness check: `/readyz` returns `200` on the deployed backend

What works locally:

- backend lint and tests pass
- dashboard production build passes
- Alembic upgrades through `0012` on a local database

What must be checked during controlled production testing:

1. Run one real Twilio call end to end.
2. Confirm the call appears in the dashboard.
3. Confirm the recording appears in the call detail view after Twilio finishes processing it.
4. Confirm bookings, transcripts, tool events, and usage persist correctly.
5. Turn call recording off when the test window ends if audio retention is no longer needed.

Read `docs/PRODUCTION_STATE.md` before making production claims.

## Local Quick Start

1. Copy `.env.example` to `.env`.
2. Backend:
   `cd backend && uv sync --dev && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
3. Dashboard:
   `cd dashboard && npm install && npm run dev`
4. Open `http://127.0.0.1:3000`

Demo logins:

- owner: `owner@trattoriamadonnina.it` / `madonnina`
- operator: `operator@ristorante.ai` / `demo-password`

## Verification Commands

Backend:

```bash
cd backend
uv run ruff check app tests
DATABASE_URL=sqlite:///./test.db uv run pytest
DATABASE_URL=sqlite:///./alembic_test.db uv run alembic upgrade head
```

Dashboard:

```bash
cd dashboard
npm run build
```

GitHub hygiene:

- keep production-impacting changes behind reviewed pull requests
- use `.github/pull_request_template.md` for risk and verification notes
- do not commit local databases, secrets, Cloud Run env files, or generated build folders

Live deployment smoke test:

```bash
FRONTEND_URL=https://your-dashboard-domain \
BACKEND_URL=https://your-api-domain \
OWNER_EMAIL=owner@trattoriamadonnina.it \
OWNER_PASSWORD=madonnina \
python3 scripts/production_smoke_test.py
```

## Repo Map

- `backend/`
  FastAPI app, auth, restaurant config, booking engine, Twilio/OpenAI Realtime bridge, public reservation API, Alembic migrations, tests, and backend deployment packaging.
- `dashboard/`
  Next.js owner/operator dashboard, operator Studio, and public reservation pages.
- `docs/`
  Handoff layer for architecture, production state, operations, integrations, and setup.
- `scripts/`
  Operational helper scripts such as secret generation and production smoke tests.

Deployment entrypoint:

- use `Makefile` targets for migrations, deploys, and smoke tests
- avoid ad hoc deployment scripts; the old duplicated deploy scripts have been removed

## Documentation Map

Read in this order if you are new:

1. `docs/README.md`
2. `docs/PRODUCTION_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SETUP.md`
5. `docs/OPERATIONS.md`
6. `docs/INTEGRATIONS.md`
7. `docs/DATABASE.md`
8. `docs/OPENAI_REALTIME_READINESS.md`

Then use the focused docs as needed:

- `docs/SETUP.md`
- `docs/OPERATIONS.md`
- `docs/INTEGRATIONS.md`
- `docs/OPENAI_REALTIME_READINESS.md`
- `docs/SYSTEM_PROMPT.md`
- `docs/APP_INTERACTIONS_FLOW.md`
- `docs/APP_INTERACTIONS_VISUAL_FLOW.md`

## Deployment Shape

Deployment target:

- frontend on Cloud Run
- backend on Cloud Run
- database on Supabase Postgres
- secrets in Google Secret Manager

Operational details are in `docs/OPERATIONS.md`.

## What Is Still Needed Before Public Production

- clean production Supabase project or a deliberate cleanup decision for the current one
- custom domains and DNS/TLS
- Sentry DSN or equivalent production error tracking activation
- current dashboard URL included in backend CORS allowed origins
- human transfer validation for only the allowed escalation cases
- public reservation create/manage/cancel validation against the live database
- first real restaurant tenant data
