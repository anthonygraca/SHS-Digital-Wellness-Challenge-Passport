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
      "/auth": "http://127.0.0.1:8000",
      "/mock-idp": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
    css: true,
  },
});
