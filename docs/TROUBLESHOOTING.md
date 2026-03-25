# Troubleshooting

## Login works but dashboard data fails

Check:

- `NEXT_PUBLIC_API_BASE_URL` points at the real backend URL
- `ALLOWED_ORIGINS` includes the dashboard origin
- frontend requests use cookie credentials
- backend cookie is `Secure` and `SameSite=None` in production

## Cloud Run deploy fails before the image build starts

Check:

- `Dockerfile` is present in the uploaded source
- `.gcloudignore` is not excluding `Dockerfile`
- if the service previously used buildpacks, deploy with `--clear-base-image`

## Backend image build fails on `pip install .`

Check backend packaging metadata in `backend/pyproject.toml`.

The backend package must include only the app package, otherwise setuptools can fail on multiple top-level package discovery.

## Public `/healthz` returns Google 404 on Cloud Run

This is expected on default `*.run.app` domains.

Use:

- `/health` for liveness
- `/readyz` for readiness

## Tool endpoints return `401`

Check:

- `X-Ristorante-Tool-Secret` header is present
- the value matches `ELEVENLABS_TOOL_SECRET`

## Personalization endpoint returns `404`

The backend could not map the inbound call to a restaurant.

Check:

- `called_number` matches `restaurants.twilio_phone`
- or `agent_id` matches `restaurants.elevenlabs_agent_id`

## Post-call webhook fails signature verification

Check:

- `ELEVENLABS_WEBHOOK_SECRET`
- `ElevenLabs-Signature` header forwarding
- raw request body verification before mutation

## Settings save works but sync is skipped

That is expected unless:

- `ELEVENLABS_API_KEY` is configured
- the restaurant has an `elevenlabs_agent_id`
- the linked agent exists and is reachable from the current environment

## Local SQLite behaves strangely after schema changes

If your local SQLite file is older than the current schema expectations:

- point `DATABASE_URL` to a fresh file
- or delete the old local dev DB and restart

Production should not rely on startup schema creation.
