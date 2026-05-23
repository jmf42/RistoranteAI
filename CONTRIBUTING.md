# Contributing

Ristorante AI is a live-staging system. Treat backend, dashboard, database, Twilio, OpenAI, and Cloud Run changes as production-sensitive unless proven otherwise.

## Start Here

Read these files before making non-trivial changes:

1. `README.md`
2. `docs/PRODUCTION_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SETUP.md`
5. `docs/OPERATIONS.md`
6. `docs/INTEGRATIONS.md`
7. `docs/DATABASE.md`
8. `docs/OPENAI_REALTIME_READINESS.md`

## Local Setup

Backend:

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Dashboard:

```bash
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Required Checks

Run the checks that match the files you changed.

Backend:

```bash
cd backend
uv run ruff check app tests
DATABASE_URL=sqlite:///./test.db uv run pytest
```

Dashboard:

```bash
cd dashboard
npm run build
```

Migrations:

```bash
cd backend
DATABASE_URL=sqlite:///./alembic_test.db uv run alembic upgrade head
```

## Pull Requests

Every pull request should explain:

- what changed
- user or operator impact
- production risk
- verification performed
- whether database migrations, secrets, environment variables, or deployment steps are needed

Use `.github/pull_request_template.md`.

## Production Safety

- Do not deploy to Cloud Run without explicit approval.
- Do not change production secrets without explicit approval.
- Do not bypass Alembic for schema changes.
- Do not weaken shared-secret auth on tool endpoints.
- Do not mix unrelated fixes into the same pull request.
- Do not commit local databases, generated build output, credentials, logs, or scratch files.

## Call Recording

Call recording is controlled by backend environment variables:

- `CALL_RECORDING_ENABLED`
- `CALL_RECORDING_CONSENT_MESSAGE`

Recorded audio is stored by Twilio. The app stores only recording metadata in `call_logs.extra_data` and streams audio to authorized dashboard users through the backend.
