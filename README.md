# SHS Digital Wellness Challenge Passport


Mobile-first AI passport for multi-week student wellness challenges (CSUB Student Health Services,
DxHub 2026). Students sign in with campus SSO, join a themed challenge, check in at events via QR,
and track progress; staff author challenges and pull reports.

See [`docs/`](docs/) for the architecture plan, requirements/use cases, and feature stories.

## Project layout

| Path | What |
|---|---|
| `backend/` | FastAPI API (Python). Auth, and future challenge/check-in/reporting endpoints. |
| `frontend/` | React + TypeScript PWA (Vite). Student and admin surfaces. |
| `docs/` | Architecture, requirements, use cases, feature stories, design prototype. |
| `data/` | Challenge source content (Stranger Things passport, challenge docs). |

Current status: **F1 — Campus SSO sign-in** (US-1) is implemented. Students authenticate via a SAML
seam (a mock IdP by default for local dev); only an opaque SSO subject + affiliation are stored — no
PHI, no password, no 9-digit ID.

## Prerequisites

- **Python 3.9+** (backend)
- **Node.js 18+** and npm (frontend)

## Getting started

The app has two parts — run them in two terminals. The frontend dev server proxies API calls to the
backend, so start the backend first.

### 1. Backend (FastAPI) — http://localhost:8000

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Verify it's up: `curl http://localhost:8000/healthz` → `{"status":"ok"}`.
Run the backend tests with `pytest -q`.

By default the backend uses a **mock SAML IdP** (`WP_AUTH_PROVIDER=mock`), so no real campus identity
provider is needed for local development. See [`backend/README.md`](backend/README.md) for the
provider seam, config env vars, and how to wire a real IdP.

### 2. Frontend (React PWA) — http://localhost:5173

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Requests to `/auth`, `/mock-idp`, and `/api` are proxied to the
backend on port 8000 (configured in `frontend/vite.config.ts`).

Run the frontend tests with `npm run test`; build for production with `npm run build`.

### 3. Try the sign-in flow

1. Open http://localhost:5173 and click **Sign in with campus SSO**.
2. The mock IdP page appears — accept the default subject (`abc@csub.edu`) and submit.
3. You land on the signed-in screen ("Signed in as student").
4. To exercise the failure path, tick **Force a failed assertion** on the mock IdP page — you'll get
   the retry prompt and no account is created.

More detail: [`backend/README.md`](backend/README.md) · [`frontend/README.md`](frontend/README.md).
