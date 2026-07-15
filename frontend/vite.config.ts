/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { manifest } from "./src/pwa/manifest";

// Dev server proxies the API paths to FastAPI so the session cookie stays
// same-origin (no CORS / SameSite friction). In production the SPA and API are
// served under the same origin, so these same relative paths work unchanged.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest,
      workbox: {
        // Workbox serves the precached index.html for ANY navigation it handles.
        // /auth/login is not a fetch — it is a top-level browser redirect into the
        // SAML IdP (see auth.ts startLogin), and /mock-idp is the IdP's own page.
        // Answer either with the SPA shell and sign-in silently dies. This never bit
        // us before only because the manifest had no icons, so the app never
        // installed and the service worker never went live; shipping icons without
        // this denylist is what would have broken it. /api and /enrollment are
        // cors-mode fetches and were never at risk — they are listed to keep the
        // rule "the SW owns the SPA's routes and nothing else" readable in one place.
        //
        // This also denylists /auth/callback, which IS a client-side route. That is
        // correct: the SAML callback is inherently online-only, so passing it to the
        // network matches today's behaviour exactly (prod serves index.html for it;
        // dev has the explicit proxy bypass below).
        navigateFallbackDenylist: [
          /^\/auth\//,
          /^\/api\//,
          /^\/mock-idp\//,
          /^\/enrollment\//,
        ],
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
