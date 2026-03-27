# Supabase Production

This repo uses Supabase as managed PostgreSQL, not as the application auth layer.

## Architectural Rule

Do not switch this app to the generic Supabase frontend-auth pattern unless you intentionally redesign the product.

Current architecture:

- FastAPI backend owns auth and session cookies
- SQLAlchemy owns persistence
- Alembic owns schema changes
- Next.js dashboard calls the backend API

Supabase is used for:

- managed PostgreSQL
- operational backups and PITR
- hosted connection endpoints

## Verified Connection Path

The verified working path from this environment is the Supabase pooler URL:

```env
postgresql+psycopg://postgres.<project-ref>:<password>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
```

Use the pooler as the default unless you have explicitly verified that the direct host works in the target runtime.

Current live secret-backed connection shape:

```env
postgresql+psycopg://postgres.<project-ref>:<password>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
```

## Production Environment Rules

```env
APP_ENV=production
AUTO_CREATE_SCHEMA=false
SEED_DEMO=false
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
JWT_SECRET=<strong-random-secret>
PII_ENCRYPTION_KEY=<strong-random-secret>
SESSION_COOKIE_SECURE=true
ALLOWED_ORIGINS=https://your-dashboard-domain.com
```

Optional integration secrets:

```env
ELEVENLABS_API_KEY=
ELEVENLABS_TOOL_SECRET=
ELEVENLABS_PERSONALIZATION_SECRET=
ELEVENLABS_WEBHOOK_SECRET=
SENTRY_DSN=
```

## Migration Discipline

Production schema changes must go through Alembic only.

Apply schema:

```bash
cd backend
uv sync --dev
DATABASE_URL='<supabase-pooler-url>' uv run alembic upgrade head
```

Check schema:

```bash
cd backend
DATABASE_URL='<supabase-pooler-url>' uv run alembic current
```

Current live Alembic version was last verified as:

- `0005 (head)`

Do not trust older docs blindly. Verify with `alembic current` before making deployment claims.

## Backup And Recovery Reality

Backups and PITR are controlled on the Supabase side, not in this repository.

For real production, confirm in Supabase:

- automated backups are enabled
- PITR is enabled if your plan supports it
- you know the retention window
- you have tested at least one restore into a non-production environment

This repo can verify schema state and runtime behavior, but it cannot replace the platform-level backup policy.

## Staging vs Production Recommendation

Keep separate Supabase projects for:

- staging
- production

The current verified environment still contains demo/staging data, so it should not be described as final production data without an intentional cleanup or a fresh project.

## Learned Operational Reality

- Supabase is working correctly as the live database.
- The database is not the current telephony bottleneck.
- The most important recent production issues were in Twilio/ElevenLabs routing, not in Postgres connectivity.
- The app currently uses the Supabase project-level Postgres user. That is workable, but a narrower app-specific DB role would be cleaner for stricter long-term production hardening.
