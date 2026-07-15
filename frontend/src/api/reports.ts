import type {
  AttendanceReport,
  EngagementReport,
  LearningOutcomeReport,
  ParticipationReport,
} from "../types/report";
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
 * `?challenge_id=N`, or nothing at all when no challenge is selected.
 *
 * Omitted rather than sent empty: the server reads a missing parameter as "the
 * challenge running right now", which is what the dashboard shows before the
 * selector has loaded and what every caller wanted before US-23 added one.
 */
function scope(challengeId?: number): string {
  return challengeId === undefined ? "" : `?challenge_id=${challengeId}`;
}

/**
 * Participation and the per-week completion funnel (FR-F1 / US-21). Defaults to
 * the campus's active challenge. Throws ApiError(404) when nothing is published,
 * or when the requested challenge is not this campus's published one.
 */
export function getParticipationReport(
  challengeId?: number,
): Promise<ParticipationReport> {
  return request<ParticipationReport>(`/participation${scope(challengeId)}`);
}

/**
 * Auto-vs-manual attendance breakdown (FR-F2 / US-22). 404s on the same condition
 * /participation does — every report route resolves its challenge the same way.
 */
export function getAttendanceReport(
  challengeId?: number,
): Promise<AttendanceReport> {
  return request<AttendanceReport>(`/attendance${scope(challengeId)}`);
}

/**
 * Content views and guide usage (FR-F3 / US-23). `challenge_id` is what US-23's
 * "both can be viewed per challenge" asks for; it is accepted by every route here
 * so the dashboard's cards always describe the same challenge.
 */
export function getEngagementReport(
  challengeId?: number,
): Promise<EngagementReport> {
  return request<EngagementReport>(`/engagement${scope(challengeId)}`);
}

/**
 * Mean assessment score per learning-outcome tag (FR-F4 / US-24). 404s on the same
 * condition the reports above do — every route here resolves its challenge the
 * same way, which is what lets the dashboard treat one 404 as "nothing published".
 *
 * US-24's Gherkin never asks for `challengeId`; it is accepted anyway, like on
 * every route here, so the dashboard's cards always describe the same challenge.
 */
export function getLearningOutcomeReport(
  challengeId?: number,
): Promise<LearningOutcomeReport> {
  return request<LearningOutcomeReport>(`/outcomes${scope(challengeId)}`);
}

/**
 * The prize-eligible drawing list as a CSV file (FR-F5 / US-26). Throws
 * ApiError(404) when nothing is published, like the reports above.
 *
 * Takes the same `challengeId` as the reports, and the dashboard passes it: the
 * export is a record an admin acts on, and a drawing run against last semester's
 * list because the download ignored the selector would be a real error.
 *
 * Fetched rather than linked so the errors land in the app's own empty/alert
 * states instead of navigating the admin to a raw JSON page — and so the
 * session cookie and VITE_API_BASE are handled the same way as every other call.
 */
export async function exportPrizeCsv(
  challengeId?: number,
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}/prize-eligible.csv${scope(challengeId)}`, {
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
