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

- `0005 (head)` — migration `0006` is local-only, not applied

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

Required backend secrets (all in Google Secret Manager):

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

- `NEXT_PUBLIC_API_BASE_URL` must be present at **build time**
- if it is wrong at build time, the dashboard ships with a bad API target

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
  --set-build-env-vars NEXT_PUBLIC_API_BASE_URL=https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app \
  --set-env-vars NODE_ENV=production,NEXT_PUBLIC_API_BASE_URL=https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app
```

## Deploying Pending Backend Changes

The following are implemented locally but not yet deployed. Deploy in this order:

1. Apply migration 0006:
   ```bash
   cd backend
   DATABASE_URL='<supabase-pooler-url>' uv run alembic upgrade head
   ```

2. Deploy backend:
   ```bash
   gcloud run deploy ristorante-ai-api \
     --project ristorante-ai-20260324-9471 \
     --region europe-west1 \
     --source backend \
     --clear-base-image \
     --allow-unauthenticated
   ```

3. Re-enable post-call webhook in ElevenLabs (see section below).

## Re-enabling the Post-Call Webhook

The webhook was auto-disabled by ElevenLabs due to 401 errors.

Root cause: `ELEVENLABS_WEBHOOK_SECRET` in GCP Secret Manager does not match what ElevenLabs uses to sign payloads.

Fix:

1. Find the webhook signing secret in ElevenLabs:
   - Go to ElevenLabs → Agent settings → **Analysis** tab (or **Advanced** tab)
   - Find the post-call webhook section — copy the signing secret shown there

2. Update the secret in GCP Secret Manager:
   ```bash
   echo -n "THE_ELEVENLABS_SIGNING_KEY" | \
     gcloud secrets versions add elevenlabs-webhook-secret \
     --project ristorante-ai-20260324-9471 \
     --data-file=-
   ```

3. Redeploy the backend (so Cloud Run picks up the new secret version).

4. Re-enable the webhook in ElevenLabs:
   - ElevenLabs → Agent settings → Analysis tab → toggle the webhook back on

5. Make a test call and verify the backend returns `200` (not `401`).

## Updating ElevenLabs Tool Secrets

If `ELEVENLABS_TOOL_SECRET` changes in GCP Secret Manager, every tool in ElevenLabs must be updated to send the new value:

- Header name: `X-Ristorante-Tool-Secret`
- Tools: `check_availability`, `create_booking`, `find_booking`, `modify_booking`, `cancel_booking`

Verify tools are working:
```bash
curl -i https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app/api/tools/health \
  -H "X-Ristorante-Tool-Secret: <secret>"
```
Expected: `{"status": "ok", "auth": "valid"}`

## Updating a User's Name in the Database

To rename a user directly:

```sql
UPDATE users
SET full_name = 'New Name'
WHERE email = 'user@example.com';
```

Connect via Cloud SQL Auth Proxy or:
```bash
gcloud sql connect <instance-name> --user=postgres --database=<db-name>
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
FRONTEND_URL=https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app \
BACKEND_URL=https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app \
OWNER_EMAIL=owner@trattoriamadonnina.it \
OWNER_PASSWORD=<password> \
python3 scripts/production_smoke_test.py
```

Telephony smoke test:

```bash
curl -i -X POST https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app/api/twilio/inbound \
  --data 'From=%2B41779802809&To=%2B41225394205&CallSid=CA_smoke_test'
```

Expected results:

- healthy AI path: HTTP `200`, XML, contains ElevenLabs `<Connect><Stream .../></Connect>` TwiML
- fallback path: HTTP `200`, XML, contains the Italian apology / transfer flow

## Common Failures

### Dashboard login works but data fails

Check:

- `NEXT_PUBLIC_API_BASE_URL`
- `ALLOWED_ORIGINS`
- cookie is `Secure` and `SameSite=None`
- frontend requests use `credentials: "include"`

### Cloud Run deploy fails before image build

Check:

- `Dockerfile` exists in the uploaded source
- `.gcloudignore` is not excluding `Dockerfile`
- use `--clear-base-image` if switching from buildpacks

### Tool endpoints return `401`

Check:

- header: `X-Ristorante-Tool-Secret`
- value matches `ELEVENLABS_TOOL_SECRET` in GCP Secret Manager
- test with `GET /api/tools/health` with the same header

### Post-call webhook returns `401`

Check:

- `ELEVENLABS_WEBHOOK_SECRET` in GCP Secret Manager matches ElevenLabs signing key
- the webhook is enabled in ElevenLabs agent settings (it may have been auto-disabled)
- redeploy backend after updating the secret

### Personalization endpoint returns `404`

Check:

- `called_number` matches `restaurants.twilio_phone`
- or `agent_id` matches `restaurants.elevenlabs_agent_id`

### Inbound telephony returns fallback unexpectedly

Check:

- `ELEVENLABS_API_KEY` is set in GCP Secret Manager
- Twilio console still points to backend `/api/twilio/inbound`
- restaurant `twilio_phone` matches the Twilio number
- restaurant `elevenlabs_agent_id` is set

### Calls fail with "quota limit exceeded"

This is an ElevenLabs billing limit. Check your usage dashboard at elevenlabs.io → Settings → Subscription. Upgrade plan or wait for billing cycle to reset.

### Public `/healthz` returns Google 404

Expected on default Cloud Run `*.run.app` domains. Use `/health` or `/readyz` instead.

### Agent is reading confirmation codes aloud

Update the system prompt — remove step 7 from NUOVA PRENOTAZIONE and remove the code from CHIUSURA. See `docs/SYSTEM_PROMPT.md`.

### Agent is asking for the caller's phone number

Ensure `caller_phone` is a `dynamic_variable` (not `llm_prompt`) in every tool that has a `caller_phone` or `customer_phone` parameter in ElevenLabs.

### Webhook auto-disabled in ElevenLabs

ElevenLabs sends an email when this happens. Fix the secret mismatch (see section above) then re-enable from agent settings.

## Backup Reality

Backups and PITR are controlled in Supabase, not in this repo.

For real production, confirm:

- automated backups enabled
- PITR enabled if your plan supports it
- retention window understood
- at least one restore tested in a non-production environment
