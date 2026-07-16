import type { Bootstrap } from "../types/bootstrap";

// Relative path: proxied to FastAPI in dev, same-origin in prod.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const EMPTY: Bootstrap = { session: null, enrollment: null, passport: null };

/**
 * Fetch the app's whole first-render payload in one request.
 *
 * Replaces the /auth/session → /enrollment → /api/passport waterfall, where each hop
 * waited on the one before to learn whether it should run at all.
 *
 * Rejects only when the network does. A non-OK response resolves to three nulls —
 * the same shape the server sends a signed-out visitor — because to every caller
 * "the server said no" and "the server said nobody" mean the same thing: show
 * sign-in. A *rejection* is different and must stay one: it is the only proof that
 * we never reached the server, which is what SessionProvider needs to tell offline
 * (fall back to the cached snapshot, US-6) from signed-out (clear it).
 */
export async function fetchBootstrap(): Promise<Bootstrap> {
  const res = await fetch(`${API_BASE}/api/bootstrap`, {
    credentials: "include",
  });
  if (!res.ok) return EMPTY;
  return (await res.json()) as Bootstrap;
}
