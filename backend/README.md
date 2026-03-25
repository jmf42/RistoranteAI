# Ristorante AI Backend

FastAPI backend for:

- auth and session cookies
- restaurant configuration
- reservation logic and capacity checks
- analytics
- ElevenLabs server tools
- ElevenLabs post-call webhook ingestion

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
uv run pytest
uv run alembic upgrade head
```

## Production Notes

- production DB is Supabase Postgres
- schema changes go through Alembic
- Cloud Run is the verified deployment target
- current live backend revision is tracked in `docs/PRODUCTION_STATE.md`
