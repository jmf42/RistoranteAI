# Testing

## Backend

Run:

```bash
cd backend
uv run ruff check app tests
uv run pytest
```

The current suite covers:

- login and session flow
- booking creation, modification, and cancellation
- availability and closure logic
- production config guards
- rate limiting primitives
- booking events and export endpoints
- multi-restaurant operator behavior

## Dashboard

Run:

```bash
cd dashboard
npm run build
```

This validates:

- route compilation
- type safety
- production bundle generation

## Local Full-Stack Check

1. start backend on `127.0.0.1:8000`
2. start dashboard on `127.0.0.1:3000`
3. log in with the demo owner account
4. verify:
   - overview loads
   - bookings list loads
   - calls list loads
   - booking history panel loads
   - settings save succeeds

## Live Production Smoke Test

Use the scripted check when you want a repeatable audit against the deployed stack.

```bash
FRONTEND_URL=https://your-dashboard-domain \
BACKEND_URL=https://your-api-domain \
OWNER_EMAIL=owner@trattoriamadonnina.it \
OWNER_PASSWORD=madonnina \
python3 scripts/production_smoke_test.py
```

What it verifies:

- frontend `/`
- frontend `/login`
- backend `/health`
- backend `/readyz`
- owner login with secure cross-origin cookie behavior
- `/api/auth/me`
- `/api/restaurants/current`
- analytics, bookings, and calls endpoints
- bookings export
- calls export
- booking events endpoint

## Important Cloud Run Note

On default Cloud Run `*.run.app` domains, `/healthz` is intercepted before the request reaches the FastAPI app. Use `/health` and `/readyz` for public deployment checks.
