# Backend — SHS Wellness Passport API

FastAPI service. F1 / US-1 implements **Campus SSO sign-in** (SAML seam with a mock IdP default).

## Run

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

- `GET /auth/login?returnTo=…` → redirects to the IdP (mock: `/mock-idp/login`).
- `POST /auth/acs` → validates the assertion, provisions/loads the `Student`, sets a session cookie.
- `GET /auth/session` → current identity or 401. `POST /auth/logout` → clears the cookie.
- `GET /mock-idp/login` → dev-only stand-in for a campus SAML IdP (only when `WP_AUTH_PROVIDER=mock`).

## Tests

```bash
pytest -q
```

Covers the three US-1 Gherkin scenarios: first-time create, returning no-duplicate, failed no-record.

## Auth provider seam

`WP_AUTH_PROVIDER=mock` (default) uses a pure-Python `MockIdp` — no native deps. Setting
`WP_AUTH_PROVIDER=saml` swaps in `SamlProvider` (python3-saml), which imports `xmlsec` lazily; install
it with the optional extra: `pip install -e '.[saml]'`. Nothing outside `app/auth/` knows which
provider is active. `WP_CAMPUS_ISSUER_MAP` (JSON) maps a SAML issuer to a `campus_id`.
