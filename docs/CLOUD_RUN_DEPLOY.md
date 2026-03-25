# Cloud Run Deploy

This file explains the verified deployment path for the live app.

## Current Verified Cloud Environment

As of `2026-03-25`:

- Google Cloud project: `ristorante-ai-20260324-9471`
- region: `europe-west1`
- backend service: `ristorante-ai-api`
- frontend service: `ristorante-ai-dashboard`

Current public URLs:

- backend: `https://ristorante-ai-api-534989834839.europe-west1.run.app`
- frontend: `https://ristorante-ai-dashboard-534989834839.europe-west1.run.app`

Read `docs/PRODUCTION_STATE.md` for the current date-stamped reality.

## Service Topology

- frontend on Cloud Run
- backend on Cloud Run
- database on Supabase Postgres
- backend secrets in Google Secret Manager

## Important Deployment Truths

### 1. Frontend API URL is build-time critical

`NEXT_PUBLIC_API_BASE_URL` must be set during the frontend build.

If you only set it as a runtime env var after the image is built, the deployed dashboard can still point to the fallback local URL.

This happened once already and caused the live frontend to call `http://127.0.0.1:8000`.

### 2. Source deploy prefers Dockerfile if one exists

`gcloud run deploy --source` behaves like this:

- if a `Dockerfile` is present in the source directory, Cloud Run will use it
- otherwise, it will use buildpacks
- if the service was previously created with buildpacks, you must pass `--clear-base-image` the first time you switch that service to Dockerfile-based source builds

Do not exclude `Dockerfile` in `.gcloudignore`. That will make Cloud Build fail before the image build starts.

### 3. Cross-origin auth requires secure cookie configuration

Because frontend and backend are on different Cloud Run domains:

- backend cookie must be `SameSite=None`
- backend cookie must be `Secure`
- frontend fetches must use `credentials: "include"`
- backend `ALLOWED_ORIGINS` must include the frontend origin

## Required Backend Runtime

Required env vars:

```env
APP_ENV=production
AUTO_CREATE_SCHEMA=false
SEED_DEMO=false
SESSION_COOKIE_SECURE=true
ALLOWED_ORIGINS=https://<frontend-domain>
```

Secrets:

```env
DATABASE_URL
JWT_SECRET
PII_ENCRYPTION_KEY
ELEVENLABS_TOOL_SECRET
ELEVENLABS_PERSONALIZATION_SECRET
ELEVENLABS_WEBHOOK_SECRET
```

Current verified secret names in Secret Manager:

- `database-url`
- `jwt-secret`
- `pii-encryption-key`
- `elevenlabs-tool-secret`
- `elevenlabs-personalization-secret`
- `elevenlabs-webhook-secret`

## Required Frontend Runtime

Build-time and runtime:

```env
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
```

## Verified Deploy Pattern

### Backend

Verified pattern:

1. keep the backend `Dockerfile` in the uploaded source bundle
2. deploy with `gcloud run deploy --source ... --clear-base-image`
3. provide runtime env vars and Secret Manager bindings

Example:

```bash
gcloud run deploy ristorante-ai-api \
  --project ristorante-ai-20260324-9471 \
  --region europe-west1 \
  --source backend \
  --clear-base-image \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --port 8080 \
  --set-env-vars 'APP_ENV=production,AUTO_CREATE_SCHEMA=false,SEED_DEMO=false,SESSION_COOKIE_SECURE=true,ALLOWED_ORIGINS=https://<frontend-domain>' \
  --set-secrets DATABASE_URL=database-url:latest,JWT_SECRET=jwt-secret:latest,PII_ENCRYPTION_KEY=pii-encryption-key:latest,ELEVENLABS_TOOL_SECRET=elevenlabs-tool-secret:latest,ELEVENLABS_PERSONALIZATION_SECRET=elevenlabs-personalization-secret:latest,ELEVENLABS_WEBHOOK_SECRET=elevenlabs-webhook-secret:latest
```

### Frontend

Verified pattern:

1. keep the frontend `Dockerfile` in the uploaded source bundle
2. deploy with `gcloud run deploy --source ... --clear-base-image`
3. set `NEXT_PUBLIC_API_BASE_URL` in both build env and runtime env

Example:

```bash
gcloud run deploy ristorante-ai-dashboard \
  --project ristorante-ai-20260324-9471 \
  --region europe-west1 \
  --source dashboard \
  --clear-base-image \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --port 8080 \
  --set-build-env-vars NEXT_PUBLIC_API_BASE_URL=https://<backend-domain> \
  --set-env-vars NODE_ENV=production,NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
```

## Deployment Order

Use this order:

1. apply database migrations to Supabase
2. deploy backend
3. deploy frontend with backend URL injected at build time
4. update backend `ALLOWED_ORIGINS` if frontend URL changed
5. run live smoke tests

## Live Smoke Test Checklist

Run at minimum:

1. backend health:
   - `GET /health`
2. backend readiness:
   - `GET /readyz`
3. backend login:
   - `POST /api/auth/login`
4. authenticated API:
   - `GET /api/analytics/overview`
   - `GET /api/bookings`
   - `GET /api/calls`
   - `GET /api/bookings/export`
   - `GET /api/calls/export`
   - `GET /api/bookings/{booking_id}/events`
5. verify `Set-Cookie` contains:
   - `HttpOnly`
   - `SameSite=None`
   - `Secure`
6. browser-origin check from the frontend domain:
   - login with `credentials: include`
   - call `/api/auth/me`
   - confirm `200`
7. load frontend `/` and confirm workspace renders

`/healthz` exists in the FastAPI app and is present in OpenAPI, but Google Cloud Run default `*.run.app` domains intercept that exact path before the request reaches the service. On Cloud Run, use `/health` for liveness and `/readyz` for readiness in public smoke checks.

Repeatable script form:

```bash
FRONTEND_URL=https://<frontend-domain> \
BACKEND_URL=https://<backend-domain> \
OWNER_EMAIL=<owner-email> \
OWNER_PASSWORD=<owner-password> \
python3 scripts/production_smoke_test.py
```

## Rollback

Cloud Run makes revision rollback straightforward.

If a new revision breaks:

- identify previous healthy revision with `gcloud run services describe`
- route traffic back to the previous revision

Do not roll back schema blindly if a newer migration has already started being used by live code.

## What Still Makes This Staging-Grade

Even though the deployment works:

- default Cloud Run domains are still in use
- the current Supabase project still contains demo/staging data
- Twilio and ElevenLabs production flows are not verified unless their real credentials are configured

So this document describes a verified live deployment, but not a fully launched public production system yet.
