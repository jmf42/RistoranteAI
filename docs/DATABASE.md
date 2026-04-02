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
- live schema version: `0005 (head)`
- migrations `0006`, `0007`, and `0008` exist locally — NOT YET applied to production

See `docs/PRODUCTION_STATE.md` for the date-stamped live environment snapshot.

## Main Tables

### `restaurants`

Restaurant operational profile:

- identity and slug (unique, indexed)
- address and timezone (default: `Europe/Rome`)
- Twilio number
- ElevenLabs agent id
- opening hours (JSON: `{"lunch": "HH:MM-HH:MM", "dinner": "HH:MM-HH:MM"}`)
- weekly_closures (JSON: list of lowercase weekday strings)
- closure_dates (JSON: list of ISO date strings `YYYY-MM-DD`)
- `turni` (JSON: list of `{name, start, end, max_covers}`)
- booking rules (JSON: `{min_party, max_party, large_group_threshold, max_advance_days, min_lead_hours}`)
- `custom_greeting` (Text, nullable) — supports `{saluto}` placeholder
- `agent_style_notes` (Text, nullable)
- escalation phone
- active/inactive state

### `users`

Application auth users:

- email (unique, indexed)
- full name
- role (`owner` or `operator`)
- password hash (bcrypt)
- active state
- `token_valid_after` (DateTime) — for JWT revocation on password change
- legacy optional `restaurant_id` (FK — single restaurant link, not indexed — **missing index**)

### `user_restaurants`

User-to-restaurant access links. This is the intended multi-restaurant access model.

- unique constraint on `(user_id, restaurant_id)`

### `bookings`

Reservation records:

- restaurant id (indexed)
- confirmation code (unique, indexed) — currently sequential (e.g. `TM-032801`) — predictable, should be randomized
- date (indexed) and time
- turno (indexed)
- party size
- `customer_name_encrypted` (Text) — AES encrypted PII
- `customer_phone_encrypted` (Text) — AES encrypted PII
- `customer_phone_hash` (String(64), indexed) — for lookups without decryption
- source (`ai_phone`, `dashboard`, `walk_in`)
- booking status (`confirmed`, `modified`, `cancelled`, `no_show`, `completed`)
- special requests (nullable)
- optional linked `customer_id` (FK, indexed)

**Missing index:** `(restaurant_id, date)` composite — used in every availability check.

### `customers`

Customer-level deduplicated entity for reporting and CRM-style flows:

- `phone_hash` (indexed) — SHA-256 of normalized phone
- `name_encrypted`, `phone_encrypted` — AES encrypted
- `booking_count`, `no_show_count`, `cancellation_count`
- `last_booking_date`
- `notes` (staff notes, plaintext)
- unique constraint on `(restaurant_id, phone_hash)`

### `booking_events`

Audit-style booking history. Powers lifecycle history in the dashboard:

- `event_type` (e.g., `created`, `modified`, `cancelled`)
- `changed_by` (e.g., `ai_phone`, `user:<user_id>`)
- `changes` (JSON — delta payload of what changed)

### `call_logs`

Call summary records:

- restaurant id (indexed)
- ElevenLabs conversation id (unique, indexed)
- `caller_phone_hash` (indexed) — hashed caller phone
- `started_at` (DateTime, indexed)
- `duration_seconds`
- `outcome` (`booking_created`, `booking_modified`, `booking_cancelled`, `info_provided`, `escalated`, `abandoned`, `tool_error`)
- `call_status` (`successful`, `failed`, `unknown`) — added in migration 0006, NOT YET deployed
- `booking_id` (FK, nullable, indexed)
- `summary` (Text)
- `transcript_preview` (Text, nullable)
- `extra_data` (JSON) — flexible metadata, not exposed in API

**Note:** `call_logs` has no `created_at` field — only `started_at` (when the call happened). Webhook delivery delay is not tracked.

## Current Migration History

| Migration | Date | Changes |
|-----------|------|---------|
| `0001` | 2026-03-24 | Initial schema: restaurants, users, bookings, call_logs |
| `0002` | 2026-03-24 | customers, booking_events, user_restaurants; customer_id on bookings |
| `0003` | 2026-03-25 | Backfill customers and booking events from existing booking data |
| `0004` | 2026-03-25 | Add missing index on `call_logs.booking_id` |
| `0005` | 2026-03-26 | Flatten `assistant_settings` JSON → `custom_greeting` + `agent_style_notes`; add `users.token_valid_after` |
| `0006` | 2026-03-28 | Add `call_status` column + index to `call_logs` — **LOCAL ONLY, NOT DEPLOYED** |
| `0007` | 2026-03-31 | Add `raw_webhook_events` inbox table — **LOCAL ONLY, NOT DEPLOYED** |
| `0008` | 2026-04-01 | Enable RLS on all public app tables; preserve backend access for `postgres` / `service_role` — **LOCAL ONLY, NOT DEPLOYED** |

The important lesson is not just the migration number. Before editing restaurant AI settings or auth token invalidation, verify:

1. latest migration file
2. current ORM model
3. live Alembic version
4. actual API payload shape used by the dashboard

## Known Missing Indexes

These indexes are missing and should be added in a future migration:

| Table | Missing Index | Priority | Why |
|-------|--------------|----------|-----|
| `users` | `restaurant_id` | High | Tenant filtering queries |
| `bookings` | `(restaurant_id, date)` composite | High | Every availability check uses this |
| `customers` | `last_booking_date` | Low | Customer recency queries |

## Production Rules

- use Alembic for schema changes — never `AUTO_CREATE_SCHEMA=true` in production
- keep `SEED_DEMO=false` in production
- keep `PII_ENCRYPTION_KEY` stable across deployments — changing it makes historical data unreadable
- keep the Supabase pooler URL as the safe default unless a direct connection is proven valid
- `call_status` column (migration 0006) must be applied before deploying the backend code that uses it
- every application table in schema `public` must keep Row Level Security enabled
- `anon` and `authenticated` should have no table access to application data

## Connection and Pooling

The backend reads `DATABASE_URL` from config.

Production-related pool settings:

- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT_SECONDS`
- `DB_POOL_RECYCLE_SECONDS`

These only apply to non-SQLite databases.

## PII Model

Booking names and phones are treated as sensitive.

Important:

- the application encrypts booking PII at rest using AES (via `PII_ENCRYPTION_KEY`)
- hashes (SHA-256) of phone numbers are stored separately for lookup without decryption
- `PII_ENCRYPTION_KEY` must stay stable — changing it makes historical encrypted data unreadable
- the salt `"ristorante-ai-pii-v2"` and 600,000 PBKDF2 iterations are hardcoded in `core/security.py`
- caller_phone_hash on call_logs is also stored but NOT exposed in the API

## Operational Notes

- the live Cloud Run deployment points at Supabase through the pooler
- backups and PITR are managed at the Supabase platform level, not from this repo
- this repo can verify migrations and runtime behavior, but backup policy requires Supabase-side confirmation
- migration `0008` is the Supabase hardening baseline for public schema tables
