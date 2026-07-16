import type { CrisisResources } from "../types/guide";
import { request } from "./http";

const PREFIX = "/api/guide";

/**
 * The hard-coded crisis card (FR-E3 / NFR-8).
 *
 * Throws on failure, unlike the null-returning wrappers elsewhere — the caller decides
 * what an outage means, and for this card the answer is not "render nothing". See
 * CrisisResources.tsx, which falls back to a built-in 988 rather than an empty dialog.
 */
export function fetchCrisisResources(): Promise<CrisisResources> {
  return request<CrisisResources>(`${PREFIX}/crisis-resources`);
}
