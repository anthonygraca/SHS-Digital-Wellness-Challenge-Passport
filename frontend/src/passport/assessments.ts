import { ApiError } from "../api/challenges";
import type { KnowledgeCheckItem, McqResult } from "../types/assessment";

// Relative path: proxied to FastAPI in dev (/api → :8000), same-origin in prod.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * The knowledge-check questions on one week, with the student's own answers.
 *
 * Returns [] on failure rather than throwing, mirroring {@link fetchPassport}: the
 * quiz is one block inside the week sheet, and a quiz outage should cost the student
 * that block, not the check-in button underneath it. An empty list is also the honest
 * answer for the common case — most weeks carry no knowledge check.
 */
export async function fetchWeekItems(
  weekNo: number,
): Promise<KnowledgeCheckItem[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/assessments/weeks/${weekNo}/items`,
      { credentials: "include" },
    );
    if (!res.ok) return [];
    return (await res.json()) as KnowledgeCheckItem[];
  } catch {
    // A dropped connection is the same story to the student as a 404: no quiz to
    // show. Caught rather than left to reject, so the sheet renders either way.
    return [];
  }
}

/**
 * Submit an MCQ answer and get it back scored (FR-E4). The score comes from this call
 * itself — there is nothing to poll.
 *
 * Throws {@link ApiError} carrying the server's message, mirroring {@link scanCheckIn},
 * so the UI can show the exact copy — "You already answered this question" (409) on a
 * second attempt.
 */
export async function submitMcq(
  itemId: number,
  answer: string,
): Promise<McqResult> {
  const res = await fetch(
    `${API_BASE}/api/assessments/items/${itemId}/responses`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer }),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail =
      typeof body?.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as McqResult;
}
