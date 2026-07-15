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
