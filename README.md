# Ristorante AI

Ristorante AI is an AI phone receptionist and restaurant operations dashboard.

The product has three connected surfaces:

- a FastAPI backend that owns auth, booking rules, analytics, and ElevenLabs/Twilio-facing endpoints
- a Next.js dashboard for restaurant owners and the platform operator
- a managed PostgreSQL database on Supabase

## Current Live State

The stack is live on Google Cloud Run and Supabase:

- frontend: `https://ristorante-ai-dashboard-534989834839.europe-west1.run.app`
- backend: `https://ristorante-ai-api-534989834839.europe-west1.run.app`
- database: Supabase Postgres, schema `0004 (head)`

Important:

- the live environment is operational
- it is still best described as `live staging`
- the current Supabase project still contains demo/staging data
- Twilio and ElevenLabs real production telephony are not fully wired yet

Read `docs/PRODUCTION_STATE.md` before making any production claims.

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
uv run pytest
uv run alembic upgrade head
```

Dashboard:

```bash
cd dashboard
npm run build
```

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
  FastAPI app, Alembic migrations, tests, and deployment packaging.
- `dashboard/`
  Next.js owner/operator dashboard.
- `docs/`
  the real handoff layer for engineering, deployment, and integrations.
- `scripts/`
  operational helper scripts such as secret generation and production smoke tests.

## Documentation Map

Read in this order if you are new:

1. `docs/LLM_GUIDE.md`
2. `docs/PRODUCTION_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DATABASE.md`
5. `docs/CLOUD_RUN_DEPLOY.md`
6. `docs/SUPABASE_PRODUCTION.md`

Then use the focused docs as needed:

- `docs/SETUP.md`
- `docs/TESTING.md`
- `docs/TROUBLESHOOTING.md`
- `docs/DDR_REVIEW.md`
- `docs/ELEVENLABS_CONFIG.md`
- `docs/TWILIO_SETUP.md`
- `docs/SYSTEM_PROMPT.md`
- `docs/TOOL_DEFINITIONS.md`

## Deployment Shape

Current verified deployment path:

- frontend on Cloud Run
- backend on Cloud Run
- database on Supabase Postgres
- secrets in Google Secret Manager

The verified deployment details are in `docs/CLOUD_RUN_DEPLOY.md`.

## What Is Still Needed Before Public Production

- clean production Supabase project or a deliberate cleanup decision for the current one
- custom domains and DNS/TLS
- Sentry DSN or equivalent production error tracking activation
- real Twilio number and routing
- real ElevenLabs agent, webhook secret, and live call verification
- first real restaurant tenant data
