import { ApiError } from "../api/challenges";
import type { CheckInResult, Passport } from "../types/passport";

// Relative path: proxied to FastAPI in dev (/api → :8000), same-origin in prod.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/** Fetch the signed-in student's passport, or null if unavailable (401/404/error). */
export async function fetchPassport(): Promise<Passport | null> {
  const res = await fetch(`${API_BASE}/api/passport`, {
    credentials: "include",
  });
  if (!res.ok) return null;
  return (await res.json()) as Passport;
}

/**
 * Record an event-QR check-in from a scanned token (US-8 core loop). Returns the
 * refreshed passport, the completed week, and a tip on success. Throws {@link ApiError}
 * carrying the server's message on failure so the UI can show the exact copy —
 * "Already completed this week" (409) or "This code is no longer valid, ask the
 * attendant" (400/403).
 */
export async function scanCheckIn(token: string): Promise<CheckInResult> {
  const res = await fetch(`${API_BASE}/api/checkins/scan`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail =
      typeof body?.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as CheckInResult;
}
