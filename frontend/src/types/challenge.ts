export interface Task {
  id: number;
  challenge_id: number;
  position: number;
  title: string;
  caption: string;
  activity_type: string;
  location: string;
  date_window_start: string | null; // ISO date "YYYY-MM-DD"
  date_window_end: string | null;
  prize: string;
  required: boolean;
  assessment_items: AssessmentItem[];
  /** Signed static token rendered as the event QR students scan to check in (US-8). */
  qr_token: string;
  created_at: string;
  updated_at: string;
}

export interface Challenge {
  id: number;
  campus_id: string;
  name: string;
  semester: string;
  start_date: string; // ISO date "YYYY-MM-DD"
  end_date: string;
  /** Selected re-skin preset (US-13); "" = default theme. */
  theme_id: string;
  status: "draft" | "published";
  tasks: Task[];
  created_at: string;
  updated_at: string;
}

/** Lightweight list-view — no tasks array. */
export interface ChallengeSummary {
  id: number;
  campus_id: string;
  name: string;
  semester: string;
  start_date: string;
  end_date: string;
  theme_id: string;
  status: "draft" | "published";
  created_at: string;
  updated_at: string;
}

export interface ChallengeCreate {
  name: string;
  semester: string;
  start_date: string;
  end_date: string;
  theme_id?: string;
}

export interface ChallengeUpdate {
  name?: string;
  semester?: string;
  start_date?: string;
  end_date?: string;
  /** "" resets to the default theme. */
  theme_id?: string;
}

export interface TaskCreate {
  title: string;
  caption?: string;
  activity_type?: string;
  location?: string;
  date_window_start?: string | null;
  date_window_end?: string | null;
  prize?: string;
  required?: boolean;
}

export interface TaskUpdate {
  title?: string;
  caption?: string;
  activity_type?: string;
  location?: string;
  date_window_start?: string | null;
  date_window_end?: string | null;
  prize?: string;
  required?: boolean;
}

export interface TaskReorder {
  task_ids: number[];
}


// ---------------------------------------------------------------------------
// Assessment items (FR-B3 / US-12)
// ---------------------------------------------------------------------------

export interface AssessmentItem {
  id: number;
  task_id: number;
  item_type: "mcq" | "reflection";
  prompt: string;
  outcome_tag: string;
  options: string[] | null;
  answer_key: string | null;
  rubric: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCQCreate {
  item_type: "mcq";
  prompt: string;
  outcome_tag: string;
  options: string[];
  answer_key: string;
}

export interface ReflectionCreate {
  item_type: "reflection";
  prompt: string;
  outcome_tag: string;
  rubric: string;
}

export type AssessmentItemCreate = MCQCreate | ReflectionCreate;

export interface AssessmentItemUpdate {
  prompt?: string;
  outcome_tag?: string;
  options?: string[];
  answer_key?: string;
  rubric?: string;
}

// ---------------------------------------------------------------------------
// Manual completion override + audit (FR-D6 / US-27)
// ---------------------------------------------------------------------------

export type CheckInMethod = "event_qr" | "staff" | "manual";
export type AuditAction = "create" | "update" | "delete";

export interface CheckIn {
  id: number;
  student_id: number;
  /** The student's SSO subject — the only identifier the Student model stores. */
  student_subject: string;
  task_id: number;
  ts: string;
  method: CheckInMethod;
  /** Set to the acting admin on a manual override; null for self check-ins. */
  verified_by: string | null;
}

export interface ManualCheckInCreate {
  student_subject: string;
  reason: string;
  ts?: string | null;
}

export interface CheckInCorrect {
  reason: string;
  method?: CheckInMethod;
  ts?: string | null;
}

export interface CheckInRemove {
  reason: string;
}

/** One row of the append-only audit ledger. */
export interface CheckInAudit {
  id: number;
  campus_id: string;
  student_id: number;
  task_id: number;
  checkin_id: number | null;
  action: AuditAction;
  actor_subject: string;
  reason: string;
  ts: string;
  /** Snapshot of the check-in before the change; null for "create". */
  prior_state: Record<string, unknown> | null;
  /** Snapshot after the change; null for "delete". */
  new_state: Record<string, unknown> | null;
}
