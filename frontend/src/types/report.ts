/** Mirrors backend/app/schemas/report.py — admin reporting (UC-10). */

import type { CheckInMethod } from "./challenge";

export interface ReportChallenge {
  id: number;
  name: string;
  semester: string;
  theme_id: string;
}

/** One rung of the funnel. A week nobody finished still arrives, with a 0. */
export interface WeekCompletion {
  task_id: number;
  week_no: number;
  title: string;
  required: boolean;
  completed_count: number;
}

/** Participation and the per-week completion funnel (FR-F1 / US-21). */
export interface ParticipationReport {
  challenge: ReportChallenge;
  total_enrollments: number;
  weeks: WeekCompletion[];
}

/** How many check-ins one capture method accounted for. */
export interface MethodCount {
  method: CheckInMethod;
  count: number;
}

/**
 * Auto-vs-manual attendance breakdown (FR-F2 / US-22). All three methods always
 * arrive, `staff` included — a structural 0 until a staff-verified capture path
 * exists. Counts only: the auto share is the client's to compute, and
 * `total_checkins` is what the buckets reconcile against.
 */
export interface AttendanceReport {
  challenge: ReportChallenge;
  total_checkins: number;
  methods: MethodCount[];
}

/** What a student can look at, and so what a content view can record. */
export type ContentRef = "week_detail" | "tip";

/** How many views one piece of content accounted for. */
export interface ContentRefCount {
  content_ref: ContentRef;
  count: number;
}

/**
 * Content views and guide usage (FR-F3 / US-23). Both refs always arrive, in a
 * fixed order. Counts only: how the views divide is the client's to compute, and
 * `total_content_views` is what the buckets reconcile against.
 *
 * `guide_sessions` is a structural 0 until the conversational guide ships (US-16)
 * — the same shape as the attendance report's `staff` bucket. The card says so
 * rather than showing a bare zero.
 */
export interface EngagementReport {
  challenge: ReportChallenge;
  total_content_views: number;
  content_views: ContentRefCount[];
  guide_sessions: number;
}

/**
 * How one learning outcome scored across the cohort (FR-F4 / US-24).
 *
 * `outcome_tag` is a plain string, not a union like `ContentRef`: the vocabulary
 * is admin-authored per challenge, so there is no set to close over.
 *
 * `mean_score` is a raw 0..1 and is `null` — never 0 — exactly when
 * `response_count` is 0. A tagged item nobody has answered has no mean, and 0
 * would paint a 0% bar that reads as a catastrophe rather than a blank.
 *
 * `human_scored_count` is how many of the responses an admin re-scored by hand
 * (US-19 / FR-E5). Counted, never filtered: an overridden score is a score, and
 * it is in `mean_score` like any other.
 */
export interface OutcomeScore {
  outcome_tag: string;
  mean_score: number | null;
  response_count: number;
  human_scored_count: number;
}

/**
 * Mean assessment score per learning-outcome tag (FR-F4 / US-24) — the report
 * that replaces hand-scoring.
 *
 * Tags arrive alphabetically, always. The other reports get their fixed order
 * from a constant on the client and the server both; this one has an open
 * vocabulary, so the order is the server's ORDER BY and nothing here re-sorts it.
 *
 * Raw scores only: rendering a mean as "84%" is this layer's job, which is why
 * `mean_score` arrives as a fraction. `total_responses` is what the buckets
 * reconcile against, and the total `mean_score` is weighted by response — not the
 * mean of the per-tag means, which would let a tag with three responses outvote
 * one with three hundred.
 */
export interface LearningOutcomeReport {
  challenge: ReportChallenge;
  total_responses: number;
  mean_score: number | null;
  total_human_scored: number;
  outcomes: OutcomeScore[];
}
