import type { AttendanceReport, ParticipationReport } from "../types/report";
import { ApiError } from "./http";

// Relative path: proxied to FastAPI in dev, same-origin in prod.
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/reports";

// Re-exported so callers get ApiError from the same module as the fetchers.
export { ApiError } from "./http";

/**
 * Not http.ts's error path: these routes answer "no active challenge" with a
 * structured `detail: {code, message}` (the same shape the enroll route uses),
 * and http.ts would surface that object where a string is expected. Unwrap both
 * shapes here — plain-string details still arrive from the auth guards.
 */
async function throwApiError(res: Response): Promise<never> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  const message =
    typeof detail === "string" ? detail : (detail?.message ?? res.statusText);
  throw new ApiError(res.status, message);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) await throwApiError(res);
  return res.json() as Promise<T>;
}

/** The server's `filename="…"`, so a download is named the same everywhere. */
function filenameFrom(disposition: string | null, fallback: string): string {
  const match = disposition?.match(/filename="([^"]+)"/);
  return match ? match[1] : fallback;
}

/**
 * Participation and the per-week completion funnel for the campus's active
 * challenge (FR-F1 / US-21). Throws ApiError(404) when nothing is published.
 */
export function getParticipationReport(): Promise<ParticipationReport> {
  return request<ParticipationReport>("/participation");
}

/**
 * Auto-vs-manual attendance breakdown for the campus's active challenge
 * (FR-F2 / US-22). 404s on the same condition /participation does — both
 * resolve the same active challenge server-side.
 */
export function getAttendanceReport(): Promise<AttendanceReport> {
  return request<AttendanceReport>("/attendance");
}

/**
 * The prize-eligible drawing list as a CSV file (FR-F5 / US-26). Throws
 * ApiError(404) when nothing is published, like the reports above.
 *
 * Fetched rather than linked so the errors land in the app's own empty/alert
 * states instead of navigating the admin to a raw JSON page — and so the
 * session cookie and VITE_API_BASE are handled the same way as every other call.
 */
export async function exportPrizeCsv(): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}/prize-eligible.csv`, {
    credentials: "include",
  });
  if (!res.ok) await throwApiError(res);
  return {
    blob: await res.blob(),
    filename: filenameFrom(
      res.headers.get("Content-Disposition"),
      "prize-eligible.csv",
    ),
  };
}
