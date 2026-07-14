import type { Session } from "../types/session";

// Relative paths: proxied to FastAPI in dev, same-origin in prod.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * Begin SP-initiated SAML sign-in. This is a top-level browser navigation, NOT a
 * fetch — SAML must redirect the whole browser to the IdP. After the IdP callback
 * the backend redirects back to returnTo (our /auth/callback route).
 */
export function startLogin(): void {
  const returnTo = `${window.location.origin}/auth/callback`;
  window.location.assign(
    `${API_BASE}/auth/login?returnTo=${encodeURIComponent(returnTo)}`,
  );
}

/** Fetch the current session, or null if not signed in. */
export async function fetchSession(): Promise<Session | null> {
  const res = await fetch(`${API_BASE}/auth/session`, {
    credentials: "include",
  });
  if (!res.ok) return null;
  return (await res.json()) as Session;
}

/** Clear the session on the server. */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
