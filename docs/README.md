# Documentation Guide

Last updated: `2026-05-10`

Use this folder as the project handoff layer. The code is the source of truth for implementation, but these docs explain what the system is, what is deployed, and how to operate it.

## Read First

1. `PRODUCTION_STATE.md`
   Current live-staging status, known blockers, and what still needs validation.
2. `ARCHITECTURE.md`
   System shape: backend, dashboard, Supabase, Twilio, and OpenAI Realtime.
3. `SETUP.md`
   Local setup, demo accounts, and verification commands.
4. `OPERATIONS.md`
   Production configuration, deployment, migrations, smoke tests, and rollout checklist.
5. `INTEGRATIONS.md`
   Twilio, OpenAI Realtime, tool endpoints, Studio endpoints, and public reservation routes.
6. `DATABASE.md`
   Tables, migrations, ownership rules, and schema-change policy.

## Reference Docs

- `LLM_GUIDE.md`
  How the voice agent is designed and where prompt/tool logic lives.
- `OPENAI_REALTIME_READINESS.md`
  Realtime implementation notes and validation checklist.
- `SYSTEM_PROMPT.md`
  Prompt reference material.
- `APP_INTERACTIONS_FLOW.md`
  Product flow notes.
- `APP_INTERACTIONS_VISUAL_FLOW.md`
  Visual flow companion notes.
- `plans/`
  Historical implementation plans.

## Current Important Caveat

The deployed backend is alive but not database-ready until the production Supabase `DATABASE_URL` secret is corrected. `/health` can return `200` while `/readyz` returns `500`; trust `/readyz` for production readiness.
