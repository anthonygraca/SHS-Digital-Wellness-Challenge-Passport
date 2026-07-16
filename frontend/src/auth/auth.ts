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

/**
 * Clear the session on the server.
 *
 * The session *read* is not here: it arrives with the enrollment and passport in one
 * payload (api/bootstrap.ts), which is the only place the app needs it. GET
 * /auth/session still exists server-side and is still the authority on the shape.
 */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
