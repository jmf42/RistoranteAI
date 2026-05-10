# Ristorante AI - Operations Makefile
# Last updated: 2026-05-10

.PHONY: help verify-backend verify-dashboard verify-all migrate-prod deploy-api deploy-dashboard smoke-test gcp-auth

# Project Config
GCP_PROJECT = ristorante-ai-20260324-9471
GCP_REGION = europe-west1
BACKEND_SERVICE = ristorante-ai-api
DASHBOARD_SERVICE = ristorante-ai-dashboard
BACKEND_URL = https://ristorante-ai-api-jc7mvuujwq-ew.a.run.app
DASHBOARD_URL = https://ristorante-ai-dashboard-jc7mvuujwq-ew.a.run.app

# Auth Config
GCP_KEY_FILE = $(PWD)/gcp-key.json
GCLOUD = gcloud
UV = uv

# Detect paths for agent environments (Mac Homebrew defaults)
ifeq ($(shell which gcloud),)
	GCLOUD = /opt/homebrew/bin/gcloud
endif
ifeq ($(shell which uv),)
	UV = /opt/homebrew/bin/uv
endif

help:
	@echo "Ristorante AI Operations"
	@echo "-----------------------"
	@echo "Verification:"
	@echo "  make verify-backend      Run backend lint and tests"
	@echo "  make verify-dashboard    Run dashboard production build"
	@echo "  make verify-all          Run all local verifications"
	@echo ""
	@echo "Deployment (requires gcloud auth or gcp-key.json):"
	@echo "  make gcp-auth            Authenticate gcloud using gcp-key.json (if present)"
	@echo "  make migrate-prod        Apply Alembic migrations to production DB"
	@echo "  make deploy-api          Deploy backend to Cloud Run"
	@echo "  make deploy-dashboard    Deploy dashboard to Cloud Run"
	@echo "  make deploy-all          Deploy both API and Dashboard"
	@echo ""
	@echo "Testing:"
	@echo "  make smoke-test          Run production smoke tests against live URLs"

gcp-auth:
	@if [ -f "$(GCP_KEY_FILE)" ]; then \
		echo "Authenticating with service account key..."; \
		$(GCLOUD) auth activate-service-account --key-file=$(GCP_KEY_FILE); \
	else \
		echo "No gcp-key.json found. Using existing gcloud session."; \
	fi

verify-backend:
	cd backend && export UV_CACHE_DIR=.uv_cache && $(UV) run ruff check app tests && $(UV) run pytest

verify-dashboard:
	cd dashboard && npm run build

verify-all: verify-backend verify-dashboard

migrate-prod:
	@echo "Applying migrations to production database..."
	cd backend && $(UV) run alembic upgrade head

deploy-api: gcp-auth
	cd backend && $(GCLOUD) run deploy $(BACKEND_SERVICE) \
		--source . \
		--project $(GCP_PROJECT) \
		--region $(GCP_REGION) \
		--update-env-vars="APP_ENV=production,AUTO_CREATE_SCHEMA=false,SEED_DEMO=false,SESSION_COOKIE_SECURE=true,ALLOWED_ORIGINS=$(DASHBOARD_URL),PUBLIC_BASE_URL=$(BACKEND_URL),PUBLIC_WEB_BASE_URL=$(DASHBOARD_URL)"

deploy-dashboard: gcp-auth
	cd dashboard && $(GCLOUD) run deploy $(DASHBOARD_SERVICE) \
		--source . \
		--project $(GCP_PROJECT) \
		--region $(GCP_REGION) \
		--set-build-env-vars="NEXT_PUBLIC_API_BASE_URL=$(BACKEND_URL)"

deploy-all: deploy-api deploy-dashboard

smoke-test:
	@echo "Running production smoke tests..."
	@if [ -z "$(OWNER_EMAIL)" ] || [ -z "$(OWNER_PASSWORD)" ]; then \
		echo "Error: OWNER_EMAIL and OWNER_PASSWORD must be set."; \
		exit 1; \
	fi
	FRONTEND_URL=$(DASHBOARD_URL) \
	BACKEND_URL=$(BACKEND_URL) \
	OWNER_EMAIL=$(OWNER_EMAIL) \
	OWNER_PASSWORD=$(OWNER_PASSWORD) \
	python3 scripts/production_smoke_test.py
