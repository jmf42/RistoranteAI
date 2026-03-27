# Database

This file is the source of truth for how persistence works in this repository.

## Production Direction

The intended production database is managed PostgreSQL.

The current verified path is:

- Supabase Postgres
- SQLAlchemy ORM in the backend
- Alembic migrations for schema control
- backend-owned authentication

This app does not use Supabase Auth as the system of record.

## Current Verified State

As of `2026-03-28`:

- provider: Supabase
- verified access path: Supabase pooler URL
- live schema version currently reports `0005 (head)`

See `docs/PRODUCTION_STATE.md` for the date-stamped live environment snapshot.

## Main Tables

### `restaurants`

Restaurant operational profile:

- identity and slug
- address and timezone
- Twilio number
- ElevenLabs agent id
- opening hours and closures
- `turni`
- booking rules
- AI/telephony configuration
- escalation phone
- active/inactive state

### `users`

Application auth users:

- email
- full name
- role
- password hash
- active state
- optional `token_valid_after` for token/session invalidation
- legacy optional `restaurant_id`

### `user_restaurants`

User-to-restaurant access links.

Use this as the intended multi-restaurant access model.

### `bookings`

Reservation records:

- restaurant id
- customer-facing confirmation code
- date and time
- turno
- party size
- encrypted customer PII
- source
- booking status
- special requests
- optional linked customer

### `customers`

Customer-level deduplicated entity for reporting and future CRM-style flows.

### `booking_events`

Audit-style booking history.

This powers booking lifecycle history and is now surfaced through the API and dashboard.

### `call_logs`

Call summary records:

- restaurant id
- ElevenLabs conversation id
- duration
- outcome
- booking link
- transcript preview
- metadata

## Current Migration History

- `0001`
  initial schema
- `0002`
  customers, booking events, multi-restaurant access
- `0003`
  backfill customers and booking events from historical bookings
- `0004`
  `call_logs.booking_id` index for production query efficiency
- `0005`
  later workspace migration introducing `users.token_valid_after` and a restaurant AI-settings shape change

The important lesson is not just the migration number. The important lesson is that this area has already drifted once between model, migration, and docs. Before editing restaurant AI settings or auth token invalidation, verify:

1. latest migration file
2. current ORM model
3. live Alembic version
4. actual API payload shape used by the dashboard

## Production Rules

- use Alembic for schema changes
- keep `AUTO_CREATE_SCHEMA=false` in production
- keep `SEED_DEMO=false` in production
- keep `PII_ENCRYPTION_KEY` stable across deployments
- keep the Supabase pooler URL as the safe default unless a direct connection is proven valid in the target environment

## Connection and Pooling

The backend reads `DATABASE_URL` from config.

Production-related pool settings now exist:

- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT_SECONDS`
- `DB_POOL_RECYCLE_SECONDS`

These only apply to non-SQLite databases.

## PII Model

Booking names and phones are treated as sensitive.

Important:

- the application encrypts booking PII at rest
- `PII_ENCRYPTION_KEY` must stay stable
- changing that key can make historical encrypted data unreadable

## Operational Notes

- the live Cloud Run deployment currently points at Supabase through the pooler
- backups and PITR are managed at the Supabase platform level, not from this repo
- this repo can verify migrations and runtime behavior, but backup policy still requires Supabase-side confirmation
- the database itself is currently healthy; recent live-call failures were caused by telephony routing, not by DB connectivity
