---
name: verify
description: Build, run, and drive the Wellness Passport app (FastAPI + Vite/React) to verify changes at the browser surface, including admin sign-in via the mock IdP.
---

# Verify the Wellness Passport app

## Launch

Backend and frontend run separately (or `make dev` for both, foreground):

```bash
cd backend && .venv/bin/uvicorn app.main:app --port 8000   # API
cd frontend && npm run dev                                  # Vite on :5173, proxies /auth, /mock-idp, /api -> :8000
```

Dev DB is `backend/wellness_passport.db` (sqlite, untracked). It ships seeded
with challenge 1 ("Stranger Things Wellness Challenge", 7 tasks with QR tokens).

## Authenticate (AUTH_PROVIDER=mock is the default)

The mock IdP posts assertion fields straight to the ACS. Mint a session with curl:

```bash
# staff/admin session
curl -s -c cookies.txt -X POST http://localhost:5173/auth/acs \
  -d "subject=staff@csub.edu&affiliation=staff&returnTo=/"
# student session: affiliation=student
```

The cookie is `wp_session`. Gotcha: the ACS 302s to `returnTo`; don't follow it
on :8000 directly (no frontend there → 404). Go through :5173 or use `-o /dev/null`.

## Simulate a student QR check-in

```bash
TOKEN=$(curl -s -b cookies.txt http://localhost:5173/api/challenges/1 | \
  python3 -c "import json,sys;c=json.load(sys.stdin);print(c['tasks'][0]['qr_token'])")
curl -s -b student-cookies.txt -X POST http://localhost:5173/api/checkins/scan \
  -H "Content-Type: application/json" -d "{\"token\":\"$TOKEN\"}"
```

## Drive the browser

No Playwright browsers installed; use `playwright-core` (npm i in a temp dir)
with the system browser:

```js
chromium.launch({ executablePath: "/usr/bin/chromium-browser", args: ["--no-sandbox"] })
```

Verify at a phone viewport first (CLAUDE.md mobile-first): `{ width: 390, height: 844 }`.
Inject the session by adding the `wp_session` cookie for `http://localhost:5173`.

Flows worth driving: `/admin` (Challenge Builder, staff only), task-row actions
(Live / Items / Check-ins / Edit), `/admin/live/:challengeId/:taskId` (live event
dashboard, polls check-ins every 5s), student `/passport` + scan.

Known harmless console 404: `/favicon.ico` (none exists).
