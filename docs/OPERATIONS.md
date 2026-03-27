# Operations

This is the single operational runbook for deployment, database, verification, and common failures.

## Live Environment

Current verified environment:

- Google Cloud project: `ristorante-ai-20260324-9471`
- region: `europe-west1`
- backend: `https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app`
- frontend: `https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app`
- database: Supabase Postgres via pooler

Current live schema version last verified:

- `0005 (head)`

Treat the current environment as live staging unless intentionally cleaned and promoted.

## Deployment Shape

- frontend on Cloud Run
- backend on Cloud Run
- database on Supabase Postgres
- secrets in Google Secret Manager

## Required Backend Runtime

```env
APP_ENV=production
AUTO_CREATE_SCHEMA=false
SEED_DEMO=false
SESSION_COOKIE_SECURE=true
ALLOWED_ORIGINS=https://<frontend-domain>
```

Required backend secrets:

```env
DATABASE_URL
JWT_SECRET
PII_ENCRYPTION_KEY
ELEVENLABS_API_KEY
ELEVENLABS_TOOL_SECRET
ELEVENLABS_PERSONALIZATION_SECRET
ELEVENLABS_WEBHOOK_SECRET
```

Current verified Secret Manager names:

- `database-url`
- `jwt-secret`
- `pii-encryption-key`
- `elevenlabs-api-key`
- `elevenlabs-tool-secret`
- `elevenlabs-personalization-secret`
- `elevenlabs-webhook-secret`

## Required Frontend Runtime

```env
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
```

Important:

- `NEXT_PUBLIC_API_BASE_URL` must be present at build time
- if it is wrong at build time, the dashboard can still ship with a bad API target

## Database Rules

- use the Supabase pooler URL by default
- use Alembic for schema changes
- keep `AUTO_CREATE_SCHEMA=false` in production
- keep `SEED_DEMO=false` in production
- keep `PII_ENCRYPTION_KEY` stable

Apply migrations:

```bash
cd backend
DATABASE_URL='<supabase-pooler-url>' uv run alembic upgrade head
```

Check current schema:

```bash
cd backend
DATABASE_URL='<supabase-pooler-url>' uv run alembic current
```

## Cloud Run Deployment Pattern

Backend:

```bash
gcloud run deploy ristorante-ai-api \
  --project ristorante-ai-20260324-9471 \
  --region europe-west1 \
  --source backend \
  --clear-base-image \
  --allow-unauthenticated
```

Frontend:

```bash
gcloud run deploy ristorante-ai-dashboard \
  --project ristorante-ai-20260324-9471 \
  --region europe-west1 \
  --source dashboard \
  --clear-base-image \
  --allow-unauthenticated \
  --set-build-env-vars NEXT_PUBLIC_API_BASE_URL=https://<backend-domain> \
  --set-env-vars NODE_ENV=production,NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
```

## Verification

Backend and dashboard:

```bash
cd backend
uv run ruff check app tests
uv run pytest

cd ../dashboard
npm run build
```

Live smoke test:

```bash
FRONTEND_URL=https://<frontend-domain> \
BACKEND_URL=https://<backend-domain> \
OWNER_EMAIL=<owner-email> \
OWNER_PASSWORD=<owner-password> \
python3 scripts/production_smoke_test.py
```

Telephony smoke test:

```bash
curl -i -X POST https://<backend-domain>/api/twilio/inbound \
  --data 'From=%2B41779802809&To=%2B41225394205&CallSid=CA_smoke_test'
```

Expected results:

- healthy AI path:
  - HTTP `200`
  - XML response
  - contains ElevenLabs `<Connect><Stream .../></Connect>` TwiML
- fallback path:
  - HTTP `200`
  - XML response
  - contains the Italian apology / transfer flow

## Common Failures

### Dashboard login works but data fails

Check:

- `NEXT_PUBLIC_API_BASE_URL`
- `ALLOWED_ORIGINS`
- cookie is `Secure` and `SameSite=None`
- frontend requests use credentials

### Cloud Run deploy fails before image build

Check:

- `Dockerfile` exists in the uploaded source
- `.gcloudignore` is not excluding `Dockerfile`
- use `--clear-base-image` if switching from buildpacks

### Tool endpoints return `401`

Check:

- `X-Ristorante-Tool-Secret`
- value matches `ELEVENLABS_TOOL_SECRET`

### Personalization endpoint returns `404`

Check:

- `called_number` matches `restaurants.twilio_phone`
- or `agent_id` matches `restaurants.elevenlabs_agent_id`

### Inbound telephony returns fallback unexpectedly

Check:

- `ELEVENLABS_API_KEY`
- Twilio console still points to backend `/api/twilio/inbound`
- restaurant `twilio_phone`
- restaurant `elevenlabs_agent_id`

### Public `/healthz` returns Google 404

That is expected on default Cloud Run `*.run.app` domains.

Use:

- `/health`
- `/readyz`

## Backup Reality

Backups and PITR are controlled in Supabase, not in this repo.

For real production, confirm:

- automated backups enabled
- PITR enabled if your plan supports it
- retention window understood
- at least one restore tested in a non-production environment
