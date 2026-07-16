/** Mirrors backend/app/schemas/assessment.py */

/**
 * The student's own stored answer to an item.
 *
 * `correct` and `feedback` are each null for exactly one item type, and the asymmetry
 * is honest rather than incidental: an MCQ has a keyed answer but composes its feedback
 * at scoring time and never stores it, while a reflection stores its feedback but has
 * no key to be right or wrong against. Each type reports what it can prove.
 */
export interface StoredResponse {
  response: string;
  score: number;
  correct: boolean | null;
  scoredBy: string;
  feedback: string | null;
  ts: string;
}

/**
 * An assessment item as the student may see it — MCQ or reflection.
 *
 * Note there is no `answer_key` and no `rubric` here, unlike the `AssessmentItem` in
 * types/challenge.ts — that type mirrors the admin schema and stays on the admin
 * surface. The server sends neither to a student, and this type is the reminder of why:
 * a client that knew the key could score itself (FR-E4), and a student who knew the
 * rubric would hold the mark scheme before writing (FR-E5).
 */
export interface KnowledgeCheckItem {
  id: number;
  weekNo: number;
  itemType: "mcq" | "reflection";
  prompt: string;
  outcomeTag: string;
  /** Empty for a reflection — there is nothing to choose between. */
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

/**
 * The result of submitting one reflection (FR-E5).
 *
 * No `correct` and no `correctOption`: a reflection has no key, and a 0.6 is neither
 * right nor wrong. `outcomeTag` arrives as its own field so the UI can render it as an
 * element rather than parse it back out of the feedback prose.
 */
export interface ReflectionResult {
  itemId: number;
  outcomeTag: string;
  score: number;
  scoredBy: string;
  feedback: string;
}
