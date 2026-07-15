import type { ParticipationReport } from "../types/report";
import { ApiError } from "./http";

// Relative path: proxied to FastAPI in dev, same-origin in prod.
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/reports";

// Re-exported so callers get ApiError from the same module as the fetchers.
export { ApiError } from "./http";

/**
 * Not http.ts's `request`: this route answers "no active challenge" with a
 * structured `detail: {code, message}` (the same shape the enroll route uses),
 * and http.ts would surface that object where a string is expected. Unwrap both
 * shapes here — plain-string details still arrive from the auth guards.
 */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string" ? detail : (detail?.message ?? res.statusText);
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

/**
 * Participation and the per-week completion funnel for the campus's active
 * challenge (FR-F1 / US-21). Throws ApiError(404) when nothing is published.
 */
export function getParticipationReport(): Promise<ParticipationReport> {
  return request<ParticipationReport>("/participation");
}
