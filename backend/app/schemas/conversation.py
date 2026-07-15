"""Schemas for conversation history (US-16, FR-E2, FR-E6)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConversationMessageOut(BaseModel):
    """A message in the conversation history."""

    id: int
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSessionOut(BaseModel):
    """A conversation session with metadata and recent messages."""

    id: int
    student_id: int
    challenge_id: int | None
    theme_name: str | None
    message_count: int
    last_message_at: datetime
    created_at: datetime
    messages: list[ConversationMessageOut]

    class Config:
        from_attributes = True


class ConversationSessionCreate(BaseModel):
    """Request to create or resume a conversation session."""

    challenge_id: int | None = None
