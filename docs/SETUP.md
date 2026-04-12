# Setup

Last updated: `2026-04-10`

## Local Fast Path

1. Copy `.env.example` to `.env`
2. Generate local secrets if needed:
   `python3 scripts/generate_secrets.py`
3. Start backend:
   `cd backend && uv sync --dev && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
4. Start dashboard:
   `cd dashboard && npm install && npm run dev`
5. Open `http://127.0.0.1:3000`

## Demo Credentials

- owner: `owner@trattoriamadonnina.it` / `madonnina`
- operator: `operator@ristorante.ai` / `demo-password`

## Local Environment Variables

### Minimum local backend config

```env
DATABASE_URL=sqlite:///./data/ristorante_ai.db
AUTO_CREATE_SCHEMA=true
SEED_DEMO=true
TOOL_SECRET=local-tool-secret
PUBLIC_BASE_URL=http://127.0.0.1:8000
OPENAI_API_KEY=
OPENAI_REALTIME_MODEL=gpt-realtime-1.5
OPENAI_REALTIME_VOICE=cedar
```

You can leave `OPENAI_API_KEY` empty until you want to run real Realtime sessions. The app will still boot, but live Realtime simulation and phone-agent behavior will fail until the key is present.

### Production-like local mode

Use Docker Postgres:

```bash
docker compose up db
```

and set:

```env
DATABASE_URL=postgresql+psycopg://ristorante:ristorante@localhost:5432/ristorante_ai
AUTO_CREATE_SCHEMA=false
SEED_DEMO=false
```

Then apply migrations:

```bash
cd backend
uv run alembic upgrade head
```

## Realtime-Specific Config

- `OPENAI_API_KEY`
  required for live Realtime sessions
- `OPENAI_REALTIME_MODEL`
  default `gpt-realtime-1.5`
- `OPENAI_REALTIME_VOICE`
  default `cedar`
- `PUBLIC_BASE_URL`
  public backend base URL used in Twilio stream and callback URLs
- `TWILIO_ACCOUNT_SID`
  required for live transfer to a human
- `TWILIO_AUTH_TOKEN`
  required for live transfer to a human

## Studio Workflow

The platform operator can tune the live agent in the dashboard:

1. login as operator
2. open `/studio`
3. preview prompt, tool schema, and session payload
4. confirm readiness checks for env, Twilio, and escalation
5. test tools against the real backend
6. run text-mode Realtime simulations
7. run the multi-scenario simulation suite after meaningful prompt/session changes
8. save the runtime config for the restaurant

Saved studio config becomes the live phone-agent configuration.

## Verification

Backend:

```bash
cd backend
uv run ruff check app tests
uv run pytest
uv run alembic upgrade head
```

Frontend:

```bash
cd dashboard
npm run build
```

## Cloud Run Note

On Cloud Run default `*.run.app` domains:

- use `/health` for liveness
- use `/readyz` for readiness

Do not rely on `/healthz` for public smoke checks, because Google intercepts it before the request reaches the app.
