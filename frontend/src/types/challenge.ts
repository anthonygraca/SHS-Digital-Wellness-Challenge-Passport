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

/** Overrides for a duplicate (US-14); omitted fields are derived server-side. */
export interface ChallengeDuplicate {
  name?: string;
  semester?: string;
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
  /**
   * Opaque: a number on the SQL backend, a "<campus>#<sso>" string on DynamoDB.
   * Nothing renders it — student_subject below is the admin-facing identifier.
   */
  student_id: number | string;
  /** The student's SSO subject — the only identifier the Student model stores. */
  student_subject: string;
  task_id: number;
  ts: string;
  method: CheckInMethod;
  /** Set to the acting admin on a manual override; null for self check-ins. */
  verified_by: string | null;
}

/** How a response's score was arrived at. Never "ai" — no scorer here is one. */
export type ScoredBy = "auto" | "human";

/** One student's scored response to an assessment item, as an admin sees it (FR-E5). */
export interface AssessmentResponse {
  id: number;
  student_id: number;
  /** The student's SSO subject — the only identifier the Student model stores. */
  student_subject: string;
  /** The chosen option for an MCQ; the written reflection otherwise. */
  response: string;
  /** 0..1. Fractional for a reflection; 0 or 1 for an MCQ. */
  score: number;
  scored_by: ScoredBy;
  /** The scorer's feedback. Null for every MCQ — that feedback is never stored. */
  ai_feedback: string | null;
  ts: string;
}

/** Set a score by hand (FR-E5). The server marks it scored_by "human". */
export interface AssessmentScoreOverride {
  score: number;
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
  /** Opaque — see CheckIn.student_id. */
  student_id: number | string;
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
