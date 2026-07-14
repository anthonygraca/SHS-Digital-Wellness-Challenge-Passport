import type { Passport } from "../types/passport";

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
 * Record a manual check-in for a week (demo stand-in for the QR scan). Returns the
 * refreshed passport so the caller can update progress, or null on failure.
 */
export async function checkIn(weekNo: number): Promise<Passport | null> {
  const res = await fetch(`${API_BASE}/api/checkins`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weekNo }),
  });
  if (!res.ok) return null;
  return (await res.json()) as Passport;
}
