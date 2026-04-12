# AGENTS.md

Use this file as the first orientation point for future coding agents working in this repository.

## Product Intent

Ristorante AI is an AI phone receptionist and restaurant operations dashboard for restaurants.

The repo exists to prove the full loop:

- Twilio and OpenAI Realtime call context entering the backend
- real reservation logic against restaurant capacity rules
- owner/operator dashboard workflows against the same source of truth

## Start Here

Read these in order:

1. `docs/LLM_GUIDE.md`
2. `docs/PRODUCTION_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/OPERATIONS.md`
5. `docs/INTEGRATIONS.md`
6. `docs/OPENAI_REALTIME_READINESS.md`

Then verify the repo state:

- `cd backend && uv run ruff check app tests`
- `cd backend && uv run pytest`
- `cd dashboard && npm run build`

## Current Ground Truth

As of `2026-04-07`:

- backend is deployed to Cloud Run
- frontend is deployed to Cloud Run
- database is Supabase Postgres
- live migration target in the repo is Alembic `0011 (head)`
- current public environment is live staging, not final public production
- local verification baseline is:
  - `cd backend && uv run ruff check app tests`
  - `cd backend && uv run pytest`
  - `cd dashboard && npm run build`

## Codebase Map

- `backend/app/main.py`
  FastAPI entrypoint, middleware, rate limiting, and health/readiness routes.
- `backend/app/api/`
  HTTP boundaries only.
- `backend/app/services/`
  booking engine, analytics, availability logic, and seeding.
- `backend/app/models/entities.py`
  SQLAlchemy source of truth.
- `backend/app/core/`
  config, security, observability, and DB wiring.
- `backend/alembic/`
  migration history.
- `dashboard/app/`
  route-level screens.
- `dashboard/components/`
  shared shell, auth UI, workspace switching, charts, and layout pieces.
- `dashboard/lib/api.ts`
  browser API wrapper with cookie credentials and request timeouts.
- `docs/`
  handoff and operations docs.

## Important Constraints

- Keep tool endpoints on shared-secret header auth.
- Keep owner/operator role separation intact.
- Keep the OpenAI Realtime prompt and session config editable from the operator studio rather than hard-coded only in source.
- Do not remove the runnable local demo flow unless you replace it with an equally usable bootstrap.
- Do not bypass Alembic for production schema changes.
- On Cloud Run default `*.run.app` domains, use `/health` and `/readyz` for public checks. `/healthz` is present in the app but intercepted before the request reaches the service.
