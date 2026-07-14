.PHONY: help install run-api run-web dev test test-api test-unit typecheck build lint lint-fix lint-commits security-deps clean

# All backend tooling goes through backend/.venv — never global pip.
# Targets call the venv binaries directly; no activation needed.
VENV := backend/.venv

help:              ## list available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:           ## create backend venv + install backend & frontend deps
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e 'backend[dev]'
	cd frontend && npm ci

run-api:           ## run the backend API (uvicorn --reload) on :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

run-web:           ## run the frontend dev server (vite) on :5173
	cd frontend && npm run dev

dev:               ## run backend + frontend together (Ctrl-C stops both)
	@echo "API  -> http://localhost:8000"
	@echo "Web  -> http://localhost:5173  (proxies /auth, /mock-idp, /api -> :8000)"
	@trap 'kill 0' INT TERM EXIT; \
	  ( cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000 ) & \
	  ( cd frontend && npm run dev ) & \
	  wait

test: test-api test-unit  ## run all tests (backend + frontend)

test-api:          ## backend tests (pytest)
	cd backend && .venv/bin/pytest -q

test-unit:         ## frontend unit + component tests (Vitest/RTL)
	cd frontend && npm test

typecheck:         ## typecheck the frontend (tsc)
	cd frontend && npx tsc -b

build:             ## production build of the frontend (tsc + vite -> PWA)
	cd frontend && npm run build

lint:              ## ruff lint + format-check on the backend (biome/TS: future)
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

lint-fix:          ## auto-fix lint + apply ruff formatting on the backend
	cd backend && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

lint-commits:      ## every non-merge commit vs main must reference an issue (#N)
	scripts/lint-commits.sh

security-deps:     ## audit dependencies for known vulnerabilities
	cd frontend && npm audit --audit-level=high
	# pip-audit is not yet a dev dependency; uncomment once added to backend[dev]:
	# cd backend && .venv/bin/pip-audit

clean:             ## remove build/test artifacts (keeps deps)
	rm -rf frontend/dist frontend/.vite backend/.pytest_cache backend/*.db
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Future layers — ported from chp-dispatch-ai-overlay as the project grows.
# Each needs tooling this repo doesn't have yet; enable a layer by adding its
# tooling, then uncommenting the target.
#
#   biome         frontend TS/React lint + format-check (add biome + config;
#                 fold into the `lint` target alongside ruff).
#   gen-api /     OpenAPI -> frontend/src/api-types.ts codegen + a drift gate.
#   check-codegen Replaces the hand-written types/session.ts. Needs an
#                 openapi-typescript step and `npm run gen:api`.
#   test-e2e /    Playwright browser tests. Needs backend[e2e] extra,
#   install-e2e   `playwright install chromium`, and docker-compose.yml.
#   up / down     Containerized stack. Needs docker-compose.yml.
#   docs /        mkdocs + PlantUML site. Needs docs/build.sh.
#   docs-serve
#   security-     Full-history secret scan (gitleaks via pinned docker image).
#   secrets       Needs docker; best paired with a CI gate.
# ---------------------------------------------------------------------------
