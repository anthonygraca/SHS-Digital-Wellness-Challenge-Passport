import type { ManifestOptions } from "vite-plugin-pwa";

/**
 * The web app manifest (US-6 / FR-C4).
 *
 * It lives in src/ rather than inline in vite.config.ts for two reasons: tsconfig
 * only includes src/, so `satisfies` below actually typechecks here, and a plain
 * exported object is the only part of "is this installable?" that a jsdom test can
 * assert. Installability itself is a browser judgement about the built artifact —
 * manifest.test.ts pins the preconditions Chrome documents, and the rest is the
 * manual preview-build check in the PR.
 */
export const manifest = {
  name: "SHS Wellness Passport",
  short_name: "Passport",
  description: "Track your weekly wellness challenge progress and prize eligibility.",

  // The installed app's user is, by definition, a student mid-challenge, and the
  // story's premise is "launch from the home screen → see my progress". "/" would
  // route through the landing, which unconditionally fetches enrollment status and
  // renders "we couldn't load your challenge" when that fetch fails — so an offline
  // launch would open on an error card. /passport reads the cached passport instead.
  // Signed-out still redirects to sign-in from there.
  start_url: "/passport",
  // Explicit: without it the scope would be inferred from start_url's directory,
  // which would put /home and /admin outside the installed app.
  scope: "/",

  display: "standalone",
  background_color: "#12100f",
  theme_color: "#ff4438",

  // PNG, not SVG, and deliberately. Chrome's install criteria require a 192x192 and
  // a 512x512; declaring an SVG instead means sizes:"any", which is the exact
  // configuration behind two open Chromium install bugs (crbug 40925759, 40911689).
  // These are committed brand assets, not build output — see docs/architecture-plan.md
  // for the rsvg-convert commands that regenerate them from the .svg sources.
  icons: [
    { src: "/icons/pwa-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icons/pwa-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    {
      src: "/icons/pwa-maskable-512.png",
      sizes: "512x512",
      type: "image/png",
      purpose: "maskable",
    },
  ],
} satisfies Partial<ManifestOptions>;
