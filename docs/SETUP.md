# Setup

## Local Fast Path

1. Copy `.env.example` to `.env`
2. Generate strong local secrets if needed:
   `python3 scripts/generate_secrets.py`
3. Start backend:
   `cd backend && uv sync --dev && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
4. Start dashboard:
   `cd dashboard && npm install && npm run dev`
5. Open `http://127.0.0.1:3000`

If you previously cleaned local generated files, these are the only two restore commands you need:

- backend: `uv sync --dev`
- dashboard: `npm install`

## Demo Credentials

- owner: `owner@trattoriamadonnina.it` / `madonnina`
- operator: `operator@ristorante.ai` / `demo-password`

## Local Database Modes

### Fastest local mode

Use SQLite:

```env
DATABASE_URL=sqlite:///./data/ristorante_ai.db
AUTO_CREATE_SCHEMA=true
SEED_DEMO=true
```

### Production-like local mode

Use local PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg://ristorante:ristorante@localhost:5432/ristorante_ai
```

Then start only the local Postgres container:

```bash
docker compose up db
```

## Managed PostgreSQL Mode

For a real managed database, use Supabase and follow:

- `docs/OPERATIONS.md`
- `docs/INTEGRATIONS.md`

Important production differences:

- `AUTO_CREATE_SCHEMA=false`
- `SEED_DEMO=false`
- use Alembic migrations
- set `SESSION_COOKIE_SECURE=true`
- set explicit `ALLOWED_ORIGINS`

## Important Environment Variables

- `DATABASE_URL`
  SQLite for quick local work, PostgreSQL for production-like work
- `AUTO_CREATE_SCHEMA`
  keep `true` only for local bootstrap
- `SEED_DEMO`
  keep `true` only for local bootstrap
- `ALLOWED_ORIGINS`
  must include the actual dashboard origin
- `JWT_SECRET`
  long random secret
- `PII_ENCRYPTION_KEY`
  must be explicit and stable in production
- `ELEVENLABS_TOOL_SECRET`
  shared secret for server tool endpoints
- `ELEVENLABS_PERSONALIZATION_SECRET`
  shared secret for personalization requests
- `ELEVENLABS_WEBHOOK_SECRET`
  required for validating post-call webhook signatures in production
- `NEXT_PUBLIC_API_BASE_URL`
  browser-visible backend URL for the dashboard

## Cloud Run Note

The verified deployment target is Cloud Run.

For public smoke checks on Cloud Run default `*.run.app` domains:

- use `/health` for liveness
- use `/readyz` for readiness

Do not depend on `/healthz` for the public Cloud Run URL.
