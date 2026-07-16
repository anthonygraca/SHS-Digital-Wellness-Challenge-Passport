import type {
  Challenge,
  ChallengeSummary,
  ChallengeCreate,
  ChallengeUpdate,
  ChallengeDuplicate,
  Task,
  TaskCreate,
  TaskUpdate,
  TaskReorder,
  AssessmentItem,
  AssessmentItemCreate,
  AssessmentItemUpdate,
  AssessmentResponse,
  AssessmentScoreOverride,
  CheckIn,
  CheckInAudit,
  CheckInCorrect,
  CheckInRemove,
  CheckInSummary,
  ManualCheckInCreate,
} from "../types/challenge";
import { request as httpRequest } from "./http";

// Re-exported so existing callers keep importing ApiError from this module.
export { ApiError } from "./http";

const PREFIX = "/api/challenges";

function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return httpRequest<T>(`${PREFIX}${path}`, init);
}

// ---------------------------------------------------------------------------
// Challenges
// ---------------------------------------------------------------------------

export function listChallenges(): Promise<ChallengeSummary[]> {
  return request<ChallengeSummary[]>("");
}

export function getChallenge(id: number): Promise<Challenge> {
  return request<Challenge>(`/${id}`);
}

export function createChallenge(data: ChallengeCreate): Promise<Challenge> {
  return request<Challenge>("", { method: "POST", body: JSON.stringify(data) });
}

export function updateChallenge(
  id: number,
  data: ChallengeUpdate,
): Promise<Challenge> {
  return request<Challenge>(`/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function publishChallenge(id: number): Promise<Challenge> {
  return request<Challenge>(`/${id}/publish`, { method: "POST" });
}

/** Deep-copy a challenge into a new draft (US-14). Returns the copy. */
export function duplicateChallenge(
  id: number,
  data: ChallengeDuplicate = {},
): Promise<Challenge> {
  return request<Challenge>(`/${id}/duplicate`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export function addTask(challengeId: number, data: TaskCreate): Promise<Task> {
  return request<Task>(`/${challengeId}/tasks`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateTask(
  challengeId: number,
  taskId: number,
  data: TaskUpdate,
): Promise<Task> {
  return request<Task>(`/${challengeId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTask(
  challengeId: number,
  taskId: number,
): Promise<void> {
  return request<void>(`/${challengeId}/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export function reorderTasks(
  challengeId: number,
  data: TaskReorder,
): Promise<Task[]> {
  return request<Task[]>(`/${challengeId}/tasks/order`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}


// ---------------------------------------------------------------------------
// Assessment items (FR-B3 / US-12)
// ---------------------------------------------------------------------------

export function listAssessmentItems(
  challengeId: number,
  taskId: number,
): Promise<AssessmentItem[]> {
  return request<AssessmentItem[]>(
    `/${challengeId}/tasks/${taskId}/items`,
  );
}

export function addAssessmentItem(
  challengeId: number,
  taskId: number,
  data: AssessmentItemCreate,
): Promise<AssessmentItem> {
  return request<AssessmentItem>(
    `/${challengeId}/tasks/${taskId}/items`,
    { method: "POST", body: JSON.stringify(data) },
  );
}

export function updateAssessmentItem(
  challengeId: number,
  taskId: number,
  itemId: number,
  data: AssessmentItemUpdate,
): Promise<AssessmentItem> {
  return request<AssessmentItem>(
    `/${challengeId}/tasks/${taskId}/items/${itemId}`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

export function deleteAssessmentItem(
  challengeId: number,
  taskId: number,
  itemId: number,
): Promise<void> {
  return request<void>(
    `/${challengeId}/tasks/${taskId}/items/${itemId}`,
    { method: "DELETE" },
  );
}

/** Every student response to one assessment item, newest first (FR-E5). */
export function listAssessmentResponses(
  challengeId: number,
  taskId: number,
  itemId: number,
): Promise<AssessmentResponse[]> {
  return request<AssessmentResponse[]>(
    `/${challengeId}/tasks/${taskId}/items/${itemId}/responses`,
  );
}

/**
 * Adjust one response's score by hand (FR-E5). The server marks it scored_by "human"
 * and keeps the scorer's feedback — the score is corrected, not the record of it.
 */
export function overrideAssessmentScore(
  challengeId: number,
  taskId: number,
  itemId: number,
  responseId: number,
  data: AssessmentScoreOverride,
): Promise<AssessmentResponse> {
  return request<AssessmentResponse>(
    `/${challengeId}/tasks/${taskId}/items/${itemId}/responses/${responseId}`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

// ---------------------------------------------------------------------------
// Manual completion override + audit (FR-D6 / US-27)
// ---------------------------------------------------------------------------

/**
 * Every check-in for a task, each with the student's subject.
 *
 * For the manual-override panel, where an admin has clicked through to act on a
 * named student. The live dashboard uses {@link getCheckInSummary} instead — it needs
 * a count, not a roster, and it is projected in a room.
 */
export function listCheckIns(
  challengeId: number,
  taskId: number,
): Promise<CheckIn[]> {
  return request<CheckIn[]>(`/${challengeId}/tasks/${taskId}/checkins`);
}

/** The live dashboard's count + recent feed — no identities (FR-D4 / US-28). */
export function getCheckInSummary(
  challengeId: number,
  taskId: number,
): Promise<CheckInSummary> {
  return request<CheckInSummary>(
    `/${challengeId}/tasks/${taskId}/checkins/summary`,
  );
}

export function createManualCheckIn(
  challengeId: number,
  taskId: number,
  data: ManualCheckInCreate,
): Promise<CheckIn> {
  return request<CheckIn>(
    `/${challengeId}/tasks/${taskId}/checkins`,
    { method: "POST", body: JSON.stringify(data) },
  );
}

export function correctCheckIn(
  challengeId: number,
  taskId: number,
  checkInId: number,
  data: CheckInCorrect,
): Promise<CheckIn> {
  return request<CheckIn>(
    `/${challengeId}/tasks/${taskId}/checkins/${checkInId}`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

/** Removal carries a body: a reason is required even to delete (FR-D6). */
export function removeCheckIn(
  challengeId: number,
  taskId: number,
  checkInId: number,
  data: CheckInRemove,
): Promise<void> {
  return request<void>(
    `/${challengeId}/tasks/${taskId}/checkins/${checkInId}`,
    { method: "DELETE", body: JSON.stringify(data) },
  );
}

export function listCheckInAudits(
  challengeId: number,
  taskId: number,
  studentSubject?: string,
): Promise<CheckInAudit[]> {
  const qs = studentSubject
    ? `?student_subject=${encodeURIComponent(studentSubject)}`
    : "";
  return request<CheckInAudit[]>(`/${challengeId}/tasks/${taskId}/audits${qs}`);
}
