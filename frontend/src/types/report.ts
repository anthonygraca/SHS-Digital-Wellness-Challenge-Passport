/** Mirrors backend/app/schemas/report.py — participation reporting (UC-10). */

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
