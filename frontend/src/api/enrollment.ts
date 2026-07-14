import type { Enrollment, EnrollmentStatus } from "../types/enrollment";
import { ApiError } from "./challenges";

// Relative path: proxied to FastAPI in dev, same-origin in prod.
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/enrollment";

async function request<T>(init: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail?.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

/** Whether the campus has a joinable challenge, and whether we're already in it. */
export function fetchEnrollmentStatus(): Promise<EnrollmentStatus> {
  return request<EnrollmentStatus>();
}

/** Join the active challenge (FR-C1). Idempotent server-side. */
export function enroll(): Promise<Enrollment> {
  return request<Enrollment>({ method: "POST" });
}
