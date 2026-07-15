/**
 * Wellness Guide chat component (US-16, FR-E2, FR-E6)
 *
 * A themed in-app assistant that answers wellness questions grounded in SHS content,
 * nudges next tasks, and links campus resources. Safety guardrails are in US-17.
 */
import { useEffect, useRef, useState } from "react";
import { sendMessage } from "../../api/guide";
import type { GuideReply } from "../../types/guide";
import styles from "./WellnessGuide.module.css";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  guideReply?: GuideReply;
}

interface WellnessGuideProps {
  themeName?: string;
  personaName?: string;
}

export function WellnessGuide({
  themeName,
  personaName = "Wellness Guide",
}: WellnessGuideProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isTyping) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const reply = await sendMessage(text);

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: reply.message,
        guideReply: reply,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Guide error:", error);

      // Fallback error message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content:
          "I'm having trouble responding right now. If you're in crisis, please call 988 (Suicide & Crisis Lifeline) or 911 for emergencies. For other questions, contact Student Health Services at (661) 654-3277.",
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleClearChat = () => {
    if (
      messages.length > 0 &&
      confirm(
        "Clear this conversation? This cannot be undone. (Your conversation history is automatically deleted after 24 hours.)"
      )
    ) {
      setMessages([]);
    }
  };

  if (!isOpen) {
    return (
      <div className={styles.container}>
        <button
          type="button"
          className={styles.fab}
          onClick={() => setIsOpen(true)}
          aria-label="Open wellness guide"
          title="Chat with your wellness guide"
        >
          💬
        </button>
      </div>
    );
  }

  return (
    <div className={styles.chatWindow}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <span>💬</span>
          <span>{personaName}</span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          {messages.length > 0 && (
            <button
              type="button"
              className={styles.closeButton}
              onClick={handleClearChat}
              aria-label="Clear conversation"
              title="Clear conversation"
              style={{ fontSize: "18px" }}
            >
              🗑️
            </button>
          )}
          <button
            type="button"
            className={styles.closeButton}
            onClick={() => setIsOpen(false)}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      </div>

      <div className={styles.messages}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>💬</div>
            <div className={styles.emptyStateTitle}>
              Ask me about wellness!
            </div>
            <div className={styles.emptyStateText}>
              I can answer questions about sleep, nutrition, physical activity,
              stress management, vision health, and campus wellness resources.
              {themeName && ` (Themed as ${themeName})`}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`${styles.message} ${styles[msg.role]}`}>
              <div className={styles.messageContent}>
                {msg.guideReply?.kind === "refusal" && (
                  <div className={styles.refusal}>{msg.content}</div>
                )}
                {msg.guideReply?.kind === "answer" && <div>{msg.content}</div>}
                {msg.guideReply?.kind === "crisis" && (
                  <>
                    <div>{msg.content}</div>
                    {msg.guideReply.crisis && (
                      <div className={styles.crisisCard}>
                        <div className={styles.crisisHeadline}>
                          {msg.guideReply.crisis.headline}
                        </div>
                        <div className={styles.crisisResources}>
                          {msg.guideReply.crisis.resources.map((resource) => (
                            <div
                              key={resource.role}
                              className={styles.crisisResource}
                            >
                              <div className={styles.resourceName}>
                                {resource.name}
                              </div>
                              <a
                                href={`tel:${resource.phone}`}
                                className={styles.resourcePhone}
                              >
                                {resource.phone}
                              </a>
                              {resource.detail && (
                                <div className={styles.resourceDetail}>
                                  {resource.detail}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
                {!msg.guideReply && <div>{msg.content}</div>}
              </div>
            </div>
          ))
        )}
        {isTyping && <div className={styles.typing}>Typing...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputContainer}>
        <textarea
          ref={inputRef}
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a wellness question..."
          rows={1}
          disabled={isTyping}
          aria-label="Message input"
        />
        <button
          type="button"
          className={styles.sendButton}
          onClick={() => void handleSend()}
          disabled={!input.trim() || isTyping}
          aria-label="Send message"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
