# Frontend — SHS Wellness Passport (PWA)

Vite + React + TypeScript. F1 / US-1 delivers the **campus SSO sign-in** screen and the post-auth
landing. Theming is token-driven (`--wp-*`) so a semester re-skin is config, not code.

## Run

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173  (proxies /auth, /mock-idp, /api → :8000)
```

Run the backend on port 8000 in parallel (see `../backend/README.md`), then open the app, click
**Sign in with campus SSO**, complete the mock IdP form, and land on the signed-in screen.

## Tests / build

```bash
npm run test           # Vitest: SSO button present, zero credential inputs, click fires sign-in
npm run build          # tsc + vite build (emits PWA manifest + service worker)
```

## Theming (semester re-skin)

Add one `[data-theme="…"]` block in `src/theme/tokens.css` and one entry in `src/theme/themes.ts`;
set `ACTIVE_THEME`. Components reference only `var(--wp-*)` — no component edits needed. `ACTIVE_THEME`
will later be sourced from the backend challenge/theme config.
