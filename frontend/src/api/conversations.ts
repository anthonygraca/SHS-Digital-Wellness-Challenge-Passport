import type { ConversationSession, ConversationSessionCreate } from "../types/conversation";
import { request } from "./http";

const PREFIX = "/api/conversations";

/**
 * Create a new conversation session or return the most recent active one.
 * US-16: Each student can have one active session at a time.
 */
export function createOrGetSession(
  payload: ConversationSessionCreate = {}
): Promise<ConversationSession> {
  return request<ConversationSession>(`${PREFIX}/sessions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Get the student's current active conversation session.
 * Returns 404 if no active session exists.
 */
export function getCurrentSession(): Promise<ConversationSession | null> {
  return request<ConversationSession>(`${PREFIX}/sessions/current`).catch(
    (err) => {
      if (err.status === 404) return null;
      throw err;
    }
  );
}

/**
 * Delete a conversation session and all its messages.
 * Students can manually clear their conversation history.
 */
export function deleteSession(sessionId: number): Promise<void> {
  return request<void>(`${PREFIX}/sessions/${sessionId}`, {
    method: "DELETE",
  });
}
