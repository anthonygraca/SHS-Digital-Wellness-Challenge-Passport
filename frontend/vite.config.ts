/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Dev server proxies the API paths to FastAPI so the session cookie stays
// same-origin (no CORS / SameSite friction). In production the SPA and API are
// served under the same origin, so these same relative paths work unchanged.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // Full-page navigations to backend paths (SAML login redirect, mock IdP page,
      // the /auth/callback landing) must reach the network — the generated service
      // worker otherwise answers every navigation with the precached app shell, which
      // would swallow the login round-trip. fetch()-based API calls are unaffected
      // (the navigation fallback only matches navigations), but denylisting the API
      // prefixes too is harmless belt-and-suspenders.
      workbox: {
        navigateFallbackDenylist: [/^\/auth/, /^\/api/, /^\/enrollment/, /^\/mock-idp/],
      },
      manifest: {
        name: "SHS Wellness Passport",
        short_name: "Passport",
        start_url: "/",
        display: "standalone",
        background_color: "#12100f",
        theme_color: "#ff4438",
        icons: [],
      },
    }),
  ],
  server: {
    proxy: {
      // Proxy the backend auth endpoints, but NOT /auth/callback — that is a
      // client-side SPA route. Without this bypass the proxy would forward the
      // post-login redirect to FastAPI, which 404s, and sign-in never completes.
      "/auth": {
        target: "http://127.0.0.1:8000",
        bypass: (req) =>
          req.url?.startsWith("/auth/callback") ? "/index.html" : undefined,
      },
      "/mock-idp": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
      // The enroll endpoints (US-3) live at /enrollment rather than under /api.
      // Without this the dev server answers them with the SPA's index.html at
      // HTTP 200, the client's `res.ok` check passes, and res.json() then chokes
      // on HTML — surfacing as "we couldn't load your challenge" on the landing.
      "/enrollment": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
    css: true,
  },
});
