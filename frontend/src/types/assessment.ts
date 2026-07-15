/** Mirrors backend/app/schemas/assessment.py */

/** The student's own stored answer to an item. */
export interface StoredResponse {
  response: string;
  score: number;
  correct: boolean;
  scoredBy: string;
  ts: string;
}

/**
 * An MCQ as the student may see it.
 *
 * Note there is no `answer_key` here, unlike the `AssessmentItem` in types/challenge.ts
 * — that type mirrors the admin schema and stays on the admin surface. The server never
 * sends the key to a student before they answer, and this type is the reminder of why:
 * a client that knew the key could score itself, which is the whole of FR-E4.
 */
export interface KnowledgeCheckItem {
  id: number;
  weekNo: number;
  prompt: string;
  outcomeTag: string;
  options: string[];
  yourResponse: StoredResponse | null;
}

/** The instant result of submitting one MCQ answer (FR-E4). */
export interface McqResult {
  itemId: number;
  outcomeTag: string;
  correct: boolean;
  score: number;
  scoredBy: string;
  correctOption: string;
  feedback: string;
}
