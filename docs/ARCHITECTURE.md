# Architecture

## System Shape

The product is intentionally split into two applications plus one managed database:

- `backend/`
  FastAPI service. This is the source of truth for auth, bookings, availability, analytics, webhook processing, and tool execution.
- `dashboard/`
  Next.js owner/operator UI.
- Supabase Postgres
  managed PostgreSQL backing the application data model.

## Core Runtime Flow

1. A caller reaches the restaurant phone line.
2. ElevenLabs handles the live voice interaction.
3. ElevenLabs calls backend tool endpoints for availability, booking creation, lookup, modification, and cancellation.
4. The backend applies booking rules and capacity logic against the database.
5. The dashboard reads the same backend state, so operators see the same truth the AI acted on.

## Backend Layers

- `app/api/`
  HTTP layer only. Authentication, validation, and status codes belong here.
- `app/services/`
  business logic. Reservation rules, analytics aggregation, availability checks, and seeding live here.
- `app/models/entities.py`
  SQLAlchemy data model.
- `app/core/`
  environment settings, DB engine/session handling, security helpers, request logging, and rate limiting.
- `app/integrations/elevenlabs.py`
  vendor boundary for transcript retrieval, agent sync checks, and webhook verification support.

## Frontend Layers

- `app/`
  route-level screens.
- `components/`
  shared dashboard shell, auth form, visual components, and workspace switching.
- `lib/api.ts`
  single browser API wrapper. This is where cookie credentials and request timeouts are enforced.
- `lib/types.ts`
  frontend-side contracts that mirror the backend payload shape.

## Important Production Decisions

### Backend Owns the Rules

The frontend never decides availability, booking status, or conflict outcomes.

### Auth Is App-Owned

This repo uses backend-owned auth and session cookies. Supabase is used for PostgreSQL, not for Supabase Auth.

### Availability Is Computed

Capacity is calculated from restaurant `turni`, booking rules, and existing bookings. There is no separate slot table.

### Observability Is In-App

The backend adds request IDs, structured JSON logs, readiness checks, and Sentry hooks.

### Abuse Protection Is Layered

The backend applies rate limiting with stricter buckets for auth, tools, and webhooks. In the current Cloud Run deployment this is in-memory and therefore instance-local.

## Current Deployment Shape

- frontend on Cloud Run
- backend on Cloud Run
- secrets in Google Secret Manager
- database on Supabase Postgres

Read `docs/CLOUD_RUN_DEPLOY.md` and `docs/PRODUCTION_STATE.md` for the current live state.
