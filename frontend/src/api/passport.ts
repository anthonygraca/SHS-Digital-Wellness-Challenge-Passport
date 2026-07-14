import type { Passport } from "../types/challenge";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * Fetch the authenticated student's passport view (US-5).
 *
 * Returns the active challenge with all weeks/tasks, their status
 * (locked/available/complete), and progress countdown.
 *
 * Throws if not authenticated or no active challenge/enrollment exists.
 */
export async function fetchPassport(): Promise<Passport> {
  const res = await fetch(`${API_BASE}/api/passport`, {
    credentials: "include",
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Not authenticated");
    }
    if (res.status === 404) {
      throw new Error("No active challenge found or you are not enrolled");
    }
    throw new Error(`Failed to fetch passport: ${res.statusText}`);
  }

  return (await res.json()) as Passport;
}
