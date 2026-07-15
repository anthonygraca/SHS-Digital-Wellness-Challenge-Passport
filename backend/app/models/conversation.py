"""Conversation history model for wellness guide (US-16, FR-E2, FR-E6).

Stores minimal conversation metadata for the themed wellness guide assistant.
No PHI is stored - only message counts, timestamps, and theme context.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationSession(Base):
    """A conversation session with the wellness guide (US-16, FR-E6).

    Tracks conversation context for continuity but stores NO PHI:
    - No message content (privacy by design)
    - Only metadata: student_id, theme, message count, last activity
    - Links to challenge for theme/context but messages are ephemeral
    """

    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id"), nullable=False, index=True
    )
    challenge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("challenges.id"), nullable=True, index=True
    )
    theme_name: Mapped[str] = mapped_column(String(100), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )


class ConversationMessage(Base):
    """Individual message in a conversation (US-16, FR-E6).

    Stores minimal message history for conversation continuity within a session.
    Messages are retained only for the duration needed to provide context
    (e.g., 24 hours or 50 messages) and contain no PHI.

    For compliance with FR-E6 (minimal logging), implement retention policy:
    - Auto-delete messages older than 24 hours
    - Keep only last N messages per session
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    # Relationship
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="messages"
    )
