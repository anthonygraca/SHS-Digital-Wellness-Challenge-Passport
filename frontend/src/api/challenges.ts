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
} from "../types/challenge";

const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/challenges";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detail?.detail ?? res.statusText);
  }
  // 204 No Content — return undefined cast to T
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
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
