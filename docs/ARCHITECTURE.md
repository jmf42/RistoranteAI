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

1. A caller reaches the restaurant phone line in Twilio.
2. Twilio sends the inbound webhook to the backend `POST /api/twilio/inbound`.
3. The backend resolves the restaurant from the called number, builds the runtime personalization payload, and calls ElevenLabs `register_call`.
4. The backend returns ElevenLabs-generated TwiML back to Twilio so the call is connected to the ElevenLabs runtime.
5. ElevenLabs handles the live voice interaction.
6. ElevenLabs calls backend tool endpoints for availability, booking creation, lookup, modification, and cancellation.
7. The backend applies booking rules and capacity logic against the database.
8. The dashboard reads the same backend state, so operators see the same truth the AI acted on.

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
  vendor boundary for transcript retrieval, agent sync checks, Twilio call registration, and webhook verification support.

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

## Telephony Safety Principle

The main supported telephony entrypoint is now backend-owned.

Use:

- Twilio inbound voice → backend `/api/twilio/inbound`

Keep:

- backend `/api/twilio/voice-fallback` only as failure handling

Do not point Twilio directly at the legacy ElevenLabs `convai/twilio/inbound_call` URL. That path returned `404` during live debugging and was the source of the English “application error” failure heard by callers.
