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
