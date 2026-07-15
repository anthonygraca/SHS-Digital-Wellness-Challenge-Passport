import type {
  Challenge,
  ChallengeSummary,
  ChallengeCreate,
  ChallengeUpdate,
  Task,
  TaskCreate,
  TaskUpdate,
  TaskReorder,
  AssessmentItem,
  AssessmentItemCreate,
  AssessmentItemUpdate,
  CheckIn,
  CheckInAudit,
  CheckInCorrect,
  CheckInRemove,
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

// ---------------------------------------------------------------------------
// Manual completion override + audit (FR-D6 / US-27)
// ---------------------------------------------------------------------------

export function listCheckIns(
  challengeId: number,
  taskId: number,
): Promise<CheckIn[]> {
  return request<CheckIn[]>(`/${challengeId}/tasks/${taskId}/checkins`);
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
