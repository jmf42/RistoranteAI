# GitHub Production Flow

This is the fast production workflow for a two-person team.

## Core Rule

`main` is production.

When code is merged into `main`, GitHub runs the checks and then deploys the backend and dashboard to Cloud Run.

## Daily Work

1. Start from the latest `main`.
2. Create a branch for the change.
3. Make the change.
4. Open a pull request.
5. Wait for GitHub checks to pass.
6. Merge the pull request yourself.
7. GitHub deploys production automatically.

No second-person approval is required in this flow. The safety gate is that checks must pass before merge.

## Why Branches Matter

A branch is a temporary workspace.

`main` is the live production line. A branch is where one person changes something without blocking or overwriting the other person.

Example:

- `main`: live production code
- `juan/fix-call-history`: Juan's current change
- `teammate/update-reservation-copy`: teammate's current change

Both branches can exist at the same time. When each one is ready and checks pass, it is merged into `main`.

## Production Deployment

GitHub workflow:

- `.github/workflows/deploy-prod.yml`

It runs after the `CI` workflow passes on `main`.

It deploys:

- backend Cloud Run service
- dashboard Cloud Run service

Then it checks:

- backend `/health`
- backend `/readyz`
- dashboard home page

If `PROD_OWNER_EMAIL` and `PROD_OWNER_PASSWORD` are configured in GitHub Secrets, it also runs the production smoke test.

## Database Changes

Database changes are separate because they are harder to undo than app deploys.

GitHub workflow:

- `.github/workflows/migrate-prod.yml`

This workflow does not run automatically. It is started manually from GitHub Actions.

To run it:

1. Open GitHub Actions.
2. Choose `Migrate Production Database`.
3. Keep `git_ref` as `main` unless intentionally running a specific commit.
4. Type `migrate-production` in the confirmation field.
5. Run the workflow.

All production schema changes must use Alembic migrations under `backend/alembic/`.

## Safe Database Pattern

Prefer safe, step-by-step migrations:

1. Add new tables or columns first.
2. Deploy code that can work with both old and new data.
3. Backfill or verify data if needed.
4. Remove old columns only in a later change.

Avoid risky one-step changes such as renaming or deleting columns at the same time as deploying code that depends on the new shape.

## GitHub Setup Required

Add these repository secrets:

- `GCP_CREDENTIALS_JSON`: Google Cloud service account JSON for deployment.
- `PROD_DATABASE_URL`: production Supabase Postgres URL for Alembic.
- `PROD_OWNER_EMAIL`: optional owner login for smoke tests.
- `PROD_OWNER_PASSWORD`: optional owner password for smoke tests.

Recommended GitHub branch rule for `main`:

- require pull request before merging
- require status checks to pass
- do not require approvals
- block direct pushes
- block force pushes

The required checks should include:

- `backend`
- `dashboard`

## Google Cloud Permissions

The deploy service account needs enough permission to deploy Cloud Run from source.

At minimum, expect:

- Cloud Run Developer
- Service Account User
- Cloud Build permissions for source builds
- Artifact Registry write access if the project stores build images there

## Rollback

For app problems:

1. Roll back the Cloud Run service to the previous revision.
2. Open a fix branch.
3. Merge the fix to `main`.

For database problems:

1. Do not assume app rollback fixes the database.
2. Use Supabase backups or a carefully written forward migration.
3. Prefer additive migrations so rollback is rarely urgent.

## Current Caveat

The production docs currently say `/readyz` may fail if the Supabase database secret is wrong.

Fix that secret before relying on automatic production deploys, because this workflow treats `/readyz` failure as a production failure.
