/**
 * Type definitions for check-in flow (US-15).
 */

export type CheckInMethod = "event_qr" | "staff" | "manual";

export interface CheckInRequest {
  task_id: number;
  method?: CheckInMethod;
}

export interface PersonalizedTip {
  /** 2-3 sentence personalized health tip grounded in SHS content */
  tip: string;
  /** Campus resource or helpful link */
  resource: string;
  /** Actionable next step */
  next_step: string;
}

export interface CheckInProgress {
  /** Number of tasks completed */
  completed_tasks: number;
  /** Total tasks in the challenge */
  total_tasks: number;
  /** Total required tasks */
  required_tasks: number;
  /** Number of required tasks not yet completed */
  remaining_required_tasks: number;
  /** Whether all required tasks are complete */
  is_prize_eligible: boolean;
}

export interface CheckInResponse {
  /** ID of the created check-in record */
  checkin_id: number;
  /** Title of the task checked in to */
  task_title: string;
  /** Timestamp of check-in */
  checked_in_at: string;
  /** Personalized health tip grounded in SHS content */
  personalized_tip: PersonalizedTip;
  /** Student's progress in the challenge */
  progress: CheckInProgress;
}
