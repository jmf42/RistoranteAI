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

The owner account maps to **Trattoria Madonnina** (UUID: `a1f59bc4-b750-4f2c-bcb1-0a703ac732c7`).

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
  long random secret (32+ bytes)
- `PII_ENCRYPTION_KEY`
  must be explicit and stable in production — changing it makes existing encrypted data unreadable
- `ELEVENLABS_TOOL_SECRET`
  shared secret for server tool endpoints — must match value configured in ElevenLabs tool headers
- `ELEVENLABS_PERSONALIZATION_SECRET`
  shared secret for personalization requests (falls back to tool secret if not set)
- `ELEVENLABS_WEBHOOK_SECRET`
  required for validating post-call webhook signatures in production — must match ElevenLabs agent signing key
- `ELEVENLABS_API_KEY`
  required for Twilio call registration, transcript retrieval, agent sync
- `NEXT_PUBLIC_API_BASE_URL`
  browser-visible backend URL for the dashboard — **required at build time**

## Verification

After starting locally:

```bash
cd backend
uv run ruff check app tests
uv run pytest
```

Expected: 95 tests pass.

```bash
cd dashboard
npm run build
```

Expected: clean build with no TypeScript errors.

## ElevenLabs Local Testing

To test tool endpoints locally, use the health check:

```bash
curl -i http://127.0.0.1:8000/api/tools/health \
  -H "X-Ristorante-Tool-Secret: local-tool-secret"
```

Expected: `{"status": "ok", "auth": "valid"}`

Note: `local-tool-secret` is the default in `.env.example`. Production uses a secret from GCP Secret Manager.

## Cloud Run Note

The verified deployment target is Cloud Run.

For public smoke checks on Cloud Run default `*.run.app` domains:

- use `/health` for liveness
- use `/readyz` for readiness

Do not depend on `/healthz` for the public Cloud Run URL — it is intercepted by Google before reaching the service.

## Running Alembic Migrations Locally

```bash
cd backend

# Apply all pending migrations
uv run alembic upgrade head

# Check current version
uv run alembic current

# Create a new migration (after changing entities.py)
uv run alembic revision --autogenerate -m "description_of_change"
```

Migration files live in `backend/alembic/versions/`. Follow the naming pattern: `YYYYMMDD_NNNN_description.py`.
