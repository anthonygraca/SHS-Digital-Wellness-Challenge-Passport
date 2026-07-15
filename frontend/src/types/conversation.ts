/** Conversation history types for wellness guide (US-16, FR-E2, FR-E6) */

export interface ConversationMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationSession {
  id: number;
  student_id: number;
  challenge_id: number | null;
  theme_name: string | null;
  message_count: number;
  last_message_at: string;
  created_at: string;
  messages: ConversationMessage[];
}

export interface ConversationSessionCreate {
  challenge_id?: number | null;
}
