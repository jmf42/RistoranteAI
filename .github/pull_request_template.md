## Summary

-

## Production Risk

- [ ] No production impact
- [ ] Backend/runtime behavior changed
- [ ] Dashboard/user-facing behavior changed
- [ ] Database migration or data change
- [ ] Secrets, environment variables, Twilio, OpenAI, or Cloud Run change

## Verification

- [ ] Backend lint: `cd backend && uv run ruff check app tests`
- [ ] Backend tests: `cd backend && DATABASE_URL=sqlite:///./test.db uv run pytest`
- [ ] Dashboard build: `cd dashboard && npm run build`
- [ ] Migration check: `cd backend && DATABASE_URL=sqlite:///./alembic_test.db uv run alembic upgrade head`
- [ ] Manual browser or live call check

Notes:

-

## Deployment Notes

-

