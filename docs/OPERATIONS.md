# Operations

Last updated: `2026-05-10`

This is the operational runbook for the OpenAI Realtime stack.

## Deployment Shape

- backend on Cloud Run
- dashboard on Cloud Run
- database on Supabase Postgres
- secrets in Google Secret Manager
- Twilio for the phone number
- OpenAI Realtime for the live voice session

## Required Backend Runtime

```env
APP_ENV=production
AUTO_CREATE_SCHEMA=false
SEED_DEMO=false
SESSION_COOKIE_SECURE=true
ALLOWED_ORIGINS=https://<dashboard-domain>
PUBLIC_BASE_URL=https://<backend-domain>
PUBLIC_WEB_BASE_URL=https://<dashboard-domain>
```

Required secrets:

```env
DATABASE_URL
JWT_SECRET
PII_ENCRYPTION_KEY
TOOL_SECRET
OPENAI_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
```

Recommended optional config:

```env
OPENAI_REALTIME_MODEL=gpt-realtime-2
OPENAI_REALTIME_VOICE=cedar
NOTIFICATION_FROM_EMAIL=reservations@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Telephony note:

- if your carrier path or hardware already applies acoustic echo cancellation / upstream AEC, set the restaurant runtime `noise_reduction_type` to `off` in `/studio` to avoid double-processing caller audio
- keep any reverse proxy in front of `WS /api/twilio/media-stream` websocket-transparent; do not terminate or buffer the realtime websocket behind a proxy layer that is not confirmed to support long-lived bidirectional audio streams cleanly
- transfer to the restaurant should stay limited to explicit caller requests, large groups, allergy/out-of-policy cases, repeated unclear audio, repeated tool failure, long unresolved calls, or technical fallback; normal booking clarification should stay in the AI flow

Compatibility note:
- the backend still accepts `ELEVENLABS_TOOL_SECRET` as an alias for `TOOL_SECRET` so an existing secret can be reused during migration.

## Required Frontend Runtime

```env
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
```

`NEXT_PUBLIC_API_BASE_URL` must be present at build time.

## Database Rules

- use Alembic for schema changes
- keep `AUTO_CREATE_SCHEMA=false` in production
- keep `SEED_DEMO=false` in production
- keep `PII_ENCRYPTION_KEY` stable

## Unified Operational Workflow

The repository includes a root `Makefile` that simplifies common tasks.

### Local Verification
```bash
make verify-all
```

### Applying Migrations
```bash
# Migration target is always 'head'
make migrate-prod
```

### Deployment to Cloud Run
```bash
# Deploys both API and Dashboard
make deploy-all
```

### Health & Smoke Tests
```bash
# Simple health check
curl -i https://<backend-domain>/health

# Full production smoke test
OWNER_EMAIL='...' OWNER_PASSWORD='...' make smoke-test
```

## Agent / CI Deployment

To allow AI agents or CI/CD pipelines to deploy autonomously without interactive login:

1. Create a Google Cloud Service Account with:
   - `Cloud Run Developer`
   - `Service Account User`
2. Generate a JSON Key for the Service Account.
3. Save it as `gcp-key.json` in the project root (this file is git-ignored).
4. Future `make deploy-*` commands will automatically detect and use this key for authentication.

## Twilio Configuration

For the production Twilio number:

- inbound voice webhook → `https://<backend-domain>/api/twilio/inbound`
- primary-handler-fails webhook → `https://<backend-domain>/api/twilio/voice-fallback`

Twilio will then use backend-generated TwiML to open:

- `wss://<backend-domain>/api/twilio/media-stream`

Important:

- Twilio `<Stream url>` does not support query strings.
- stream auth is passed with Twilio custom `<Parameter>` values and validated by the backend when the websocket starts.
- inbound TwiML must open `<Connect><Stream>` immediately; do not put `<Gather>` before the stream because it can prevent Twilio from starting the WebSocket.
- mid-call DTMF `1` is handled inside the media stream as the human-escape path.
- call recording is off by default. For controlled audio QA, set `CALL_RECORDING_ENABLED=true`; the backend plays `CALL_RECORDING_CONSENT_MESSAGE`, starts Twilio recording, stores recording metadata in `call_logs.extra_data`, and serves playback through the authenticated dashboard call detail view.

The stream status callback is generated automatically as:

- `https://<backend-domain>/api/twilio/status`

When call recording is enabled, the recording status callback is generated automatically as:

- `https://<backend-domain>/api/twilio/recording-status`

## Production Readiness Checklist

Before switching real traffic:

1. `OPENAI_API_KEY` is present and valid.
2. `PUBLIC_BASE_URL` matches the backend public domain.
3. `TOOL_SECRET` is configured and `/api/tools/health` returns `auth: valid`.
4. Alembic is at `head`.
5. `/health` and `/readyz` both return `200`.
6. The dashboard builds with the correct `NEXT_PUBLIC_API_BASE_URL`.
7. `/studio` loads for the operator account.
8. `/studio` readiness checks match the deployed environment.
9. A real tool test works from `/studio`.
10. A real text simulation works from `/studio`.
11. A scenario-suite run passes for the target restaurant after any major prompt/config change.
12. A real Twilio inbound test call completes through the OpenAI bridge.
13. Public reservation create/manage/cancel flows work for the target restaurant.
14. Email notifications are either configured and sending, or deliberately left disabled for the controlled test.

## Legacy Verification Commands (Direct)

Backend:

```bash
cd backend
uv run ruff check app tests
uv run pytest
```

Frontend:

```bash
cd dashboard
npm run build
```

Manual checks:

```bash
curl -i https://<backend-domain>/health
curl -i https://<backend-domain>/readyz
curl -i https://<backend-domain>/api/tools/health \
  -H "X-Ristorante-Tool-Secret: <tool-secret>"
```

## Failure Patterns To Watch

- Twilio cannot open the websocket
  usually wrong `PUBLIC_BASE_URL`, wrong domain, or websocket ingress issue
- realtime session errors immediately
  usually missing or invalid `OPENAI_API_KEY`
- tool failures during calls
  inspect backend logs and `call_logs.extra_data.tool_events`
- escalation does not transfer
  usually missing `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, or `escalation_phone`
- too many calls transfer to the restaurant
  inspect `/studio` prompt/config and confirm the default prompt still treats transfer as a last resort
- wrong live behavior after tuning
  inspect `/studio`, saved prompt override, and `openai_realtime_settings`

## Rollback Principle

Rollback is operational:

- restore previous Cloud Run revision
- restore previous Twilio webhook target if needed
- keep the database as-is unless a schema rollback is explicitly planned

Do not rely on git alone as your rollback plan for telephony.
