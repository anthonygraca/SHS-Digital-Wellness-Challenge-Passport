/** Mirrors backend/app/schemas/guide.py — the wellness guide's crisis routing (FR-E3). */

/**
 * Which resource this is, independent of what it is called or what its number is.
 *
 * Both `name` and `phone` are per-campus deploy config (NFR-4), so `role` is the only
 * field here that is the same in every deployment. The UI keys off it — ordering,
 * emphasis, icon — and never off the prose or the digits.
 */
export type CrisisResourceRole =
  | "lifeline"
  | "campus_counseling"
  | "shs_front_desk";

export interface CrisisResource {
  role: CrisisResourceRole;
  name: string;
  phone: string;
  detail: string | null;
}

export interface CrisisResources {
  headline: string;
  /** Ordered by the server, lifeline first. Render in the order given; do not sort. */
  resources: CrisisResource[];
}

/**
 * The guide's reply to one message. `kind` is the discriminator, in the same spirit as
 * `itemType` in types/assessment.ts — three renderings, chosen by a field rather than by
 * matching on prose.
 *
 * Unused on this branch: there is no chat surface yet (that is US-16), and the only
 * thing rendering guide data today is the crisis affordance, which reads
 * `GET /api/guide/crisis-resources`. It is declared here because the contract exists and
 * is tested server-side, and because whoever builds the chat should not have to
 * re-derive it from the Python.
 */
export interface GuideReply {
  kind: "answer" | "refusal" | "crisis";
  message: string;
  refusalReason: "medical" | "out_of_scope" | null;
  crisis: CrisisResources | null;
}
