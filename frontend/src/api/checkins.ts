/**
 * API client for check-in endpoints (US-15, US-8).
 */
import type {
  CheckInRequest,
  CheckInResponse,
  CheckInProgress,
} from "../types/checkin";
import { ApiError } from "./challenges";

const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/checkins-v2";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    console.error("API Error - Status:", res.status);
    console.error("API Error - Detail:", detail);
    console.error("API Error - Detail.detail:", detail?.detail);
    
    // Extract string message from detail
    const message = typeof detail?.detail === 'string' 
      ? detail.detail 
      : JSON.stringify(detail?.detail || detail || res.statusText);
    
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

/**
 * Check in to a task and receive a personalized tip (US-15).
 * 
 * The response includes:
 * - A personalized health tip grounded in SHS content
 * - Campus resources and next steps
 * - Progress metrics and prize eligibility status
 * 
 * This call is idempotent - checking in to the same task multiple times
 * returns the existing check-in without generating duplicate tips.
 */
export function checkIn(data: CheckInRequest): Promise<CheckInResponse> {
  return request<CheckInResponse>("", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Get a student's progress in a specific challenge.
 * 
 * Returns metrics about:
 * - Completed tasks count
 * - Required tasks remaining
 * - Prize eligibility status
 */
export function getProgress(challengeId: number): Promise<CheckInProgress> {
  return request<CheckInProgress>(`/progress/${challengeId}`);
}
