# Architecture

## System Shape

The product is intentionally split into two applications plus one managed database:

- `backend/`
  FastAPI service. Source of truth for auth, bookings, availability, analytics, webhook processing, and tool execution.
- `dashboard/`
  Next.js owner/operator UI. All business logic stays in the backend.
- Supabase Postgres
  managed PostgreSQL backing the application data model.

## Core Runtime Flow

```
Caller → Twilio → POST /api/twilio/inbound
                       │
                       ├─ Resolve restaurant by twilio_phone
                       ├─ Call ElevenLabs register_call()
                       └─ Return TwiML to Twilio
                                │
                          ElevenLabs handles voice
                                │
                    ┌───────────┴───────────┐
                    │                       │
          POST /api/integrations/    POST /api/tools/*
          elevenlabs/twilio-         (check_availability,
          personalization            create_booking,
          (dynamic variables)        find_booking,
                                     modify_booking,
                                     cancel_booking)
                                           │
                                    PostgreSQL / Supabase
                                           │
                         POST /api/webhooks/elevenlabs/post-call
                         (call summary, outcome, transcript)
                                           │
                                    Dashboard reads state
```

1. A caller reaches the restaurant phone line in Twilio.
2. Twilio sends the inbound webhook to `POST /api/twilio/inbound`.
3. The backend resolves the restaurant from the called number, calls ElevenLabs `register_call`, and returns ElevenLabs-generated TwiML to Twilio.
4. Twilio connects the call to ElevenLabs.
5. ElevenLabs handles the live voice interaction.
6. **During the call:** ElevenLabs calls the personalization endpoint once for context, then calls tool endpoints for booking operations.
7. **After the call:** ElevenLabs fires the post-call webhook with summary, transcript, and call metadata.
8. The dashboard reads the same backend state — operators see the same truth the AI acted on.

## Dynamic Variables Flow

The personalization endpoint (`POST /api/integrations/elevenlabs/twilio-personalization`) builds the full context injected into ElevenLabs at call start:

```
Restaurant DB record
      │
      ▼
personalization.py
      │
      ├─ restaurant_id, restaurant_name, address, timezone
      ├─ opening_hours, weekly_closures, closure_dates
      ├─ turni_description, large_group_threshold
      ├─ caller_phone, called_number, call_sid
      ├─ current_date, current_time, current_day_of_week (from server clock)
      ├─ agent_style_notes
      └─ greeting (resolves {saluto} → Buongiorno/Buonasera by hour)
            │
            ▼
    ElevenLabs dynamic variables
    (injected as {{variable_name}} in system prompt and first message)
```

## Backend Layers

- `app/api/`
  HTTP layer only. Authentication, validation, and status codes belong here.
- `app/services/`
  Business logic. Reservation rules, analytics aggregation, availability checks, seeding.
- `app/models/entities.py`
  SQLAlchemy data model. Single source of truth for table shape.
- `app/core/`
  Environment settings, DB engine/session, security helpers, request logging, rate limiting, in-memory cache.
- `app/integrations/elevenlabs.py`
  Vendor boundary for transcript retrieval, agent sync checks, Twilio call registration, webhook verification.

## Frontend Layers

- `dashboard/app/`
  Route-level screens (Home, Bookings, Calls, Capacity, Settings, Admin, Login).
- `dashboard/components/`
  Shared dashboard shell, auth form, visual components (TrendChart, Heatmap, CapacityBars, StatCard), workspace switching.
- `dashboard/lib/api.ts`
  Single browser API wrapper. Cookie credentials, 15-second timeout, `ApiError` class.
- `dashboard/lib/types.ts`
  TypeScript contracts that mirror backend payload shapes.

## Auth Flow

```
Browser → POST /api/auth/login (email + password)
               │
               ├─ Verify bcrypt hash
               ├─ Issue JWT
               └─ Set HttpOnly cookie (Secure, SameSite=None)
                        │
               All subsequent requests include cookie
                        │
               GET /api/auth/me → SessionUser + restaurant_ids
```

Token revocation uses `User.token_valid_after` — tokens issued before this timestamp are rejected.

## Availability Computation

There is no slot table. Availability is computed on demand:

```
check_availability(date, time, party_size)
      │
      ├─ Validate restaurant is open (opening_hours, weekly_closures, closure_dates)
      ├─ Validate booking rules (min_party, max_party, max_advance_days, min_lead_hours)
      ├─ Resolve turno for requested time
      ├─ COUNT existing confirmed bookings in same turno + date
      ├─ Compare against turno.max_covers
      └─ Return available/unavailable + alternatives if unavailable
```

## Important Production Decisions

### Backend Owns the Rules

The frontend never decides availability, booking status, or conflict outcomes. All decisions are made in `app/services/`.

### Auth Is App-Owned

Backend-owned JWT auth with session cookies. Supabase is used for PostgreSQL only, not for Supabase Auth.

### Availability Is Computed

Capacity is calculated from restaurant `turni`, booking rules, and existing bookings. No separate slot table.

### PII Is Encrypted

Customer names and phone numbers are encrypted at rest (`AES` via `PII_ENCRYPTION_KEY`). Phone hashes are stored separately for lookups.

### Observability Is In-App

The backend adds request IDs, structured JSON logs, readiness checks (`/readyz` queries the DB), and Sentry hooks.

### Abuse Protection Is Layered

Rate limiting with stricter buckets for auth, tools, and webhooks. In the current Cloud Run deployment this is in-memory and therefore instance-local (resets on cold start).

## Current Deployment Shape

- frontend on Cloud Run (`ristorante-ai-dashboard`, `europe-west1`)
- backend on Cloud Run (`ristorante-ai-api`, `europe-west1`)
- secrets in Google Secret Manager
- database on Supabase Postgres

## Known Architecture Gaps

These are documented issues that exist but have not been fixed yet:

| Gap | Severity | Notes |
|-----|---------|-------|
| No Twilio signature validation on `/api/twilio/inbound` | Critical | Anyone can POST fake inbound calls |
| Webhook signature check is optional | High | Remove the `if` guard — should always verify |
| Call sync fires on every GET `/calls` | High | Should be a background job |
| No pagination on calls/bookings | High | Unbounded queries, memory risk |
| Heatmap uses UTC not local timezone | Medium | Analytics show wrong busy hours |
| Confirmation codes are sequential | Medium | Predictable and enumerable |
| No composite index on `(restaurant_id, date)` | High | Slow availability checks |
| Operator role not scoped to restaurants | Medium | Operators can access any restaurant |

## Telephony Safety Principle

The main supported telephony entrypoint is backend-owned.

Use:

- Twilio inbound voice → backend `/api/twilio/inbound`

Keep:

- backend `/api/twilio/voice-fallback` only as failure handling

Do not point Twilio directly at the legacy ElevenLabs `convai/twilio/inbound_call` URL. That path returned `404` during live debugging.

Read `docs/OPERATIONS.md` and `docs/PRODUCTION_STATE.md` for the current live state.
