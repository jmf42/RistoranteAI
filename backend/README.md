# Ristorante AI Backend

Last updated: `2026-05-10`

FastAPI backend for:

- auth and session cookies
- restaurant configuration
- reservation logic and capacity checks
- analytics
- public online reservation creation and guest manage links
- Twilio inbound voice routing
- OpenAI Realtime voice orchestration
- server-side booking tool execution for the phone agent

## Local Run

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Verification

```bash
cd backend
uv run ruff check app tests
DATABASE_URL=sqlite:///./test.db uv run pytest
DATABASE_URL=sqlite:///./alembic_test.db uv run alembic upgrade head
```

## Production Notes

- production DB is Supabase Postgres
- schema changes go through Alembic
- Cloud Run is the verified deployment target
- current live backend revision is tracked in `docs/PRODUCTION_STATE.md`
- `/readyz` must pass before treating the deployed backend as production-ready
- OpenAI Realtime readiness and docs contrast are tracked in `docs/OPENAI_REALTIME_READINESS.md`
- operator prompt/session controls and regression simulation endpoints are in `app/api/studio.py`
- public reservation endpoints are in `app/api/public.py`
- live prompt policy keeps human transfer as a last resort; normal booking clarification stays with the AI agent
