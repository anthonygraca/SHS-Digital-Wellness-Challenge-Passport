"""Conversation endpoints for wellness guide (US-16, FR-E2, FR-E6).

Students chat with a themed wellness guide that answers questions grounded in
SHS content, nudges next tasks, and links campus resources.

Note: This router stores conversation history but delegates actual message handling
to the existing /api/guide/messages endpoint which has all the safety guardrails.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_student
from app.config import Settings, get_settings
from app.db import get_db
from app.models.challenge import Challenge, CheckIn, Task
from app.models.conversation import ConversationMessage, ConversationSession
from app.services.guide import WellnessGuide, get_wellness_guide
from app.services.guide_safety import answer_message

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationRequest(BaseModel):
    """Request body for sending a message to the wellness guide."""

    message: str = Field(
        ..., description="The student's wellness question or message", min_length=1
    )
    challenge_id: int | None = Field(
        None, description="Optional challenge ID for themed context"
    )


class ConversationResponse(BaseModel):
    """Response from the wellness guide (US-16)."""

    message: str = Field(..., description="The guide's response")
    next_task_nudge: str | None = Field(
        None, description="Optional nudge about the next available task"
    )
    theme_name: str | None = Field(None, description="The active theme name")
    progress: dict | None = Field(None, description="Student's progress in the challenge")
    session_id: int = Field(..., description="Conversation session ID")


class ConversationHistoryResponse(BaseModel):
    """Response for retrieving conversation history."""

    session_id: int
    theme_name: str | None
    message_count: int
    messages: list[dict]
    created_at: datetime
    last_message_at: datetime


@router.post("/", response_model=ConversationResponse)
def send_message(
    request: ConversationRequest,
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(get_current_student)],
    guide: Annotated[WellnessGuide, Depends(get_wellness_guide)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Send a message to the wellness guide and get a response (US-16, FR-E2, FR-E6).

    This endpoint:
    1. Creates or retrieves an active conversation session
    2. Uses the existing guide_safety.answer_message() for safety guardrails
    3. Stores the user message and assistant response
    4. Returns the guide's response

    The guide response has all safety guardrails from US-17:
    - Crisis detection and routing
    - Medical advice refusal
    - Out-of-scope deflection
    """
    student_id = claims["student_id"]
    campus_id = claims["campus_id"]

    # 1. Get or create conversation session
    session = _get_or_create_session(
        db, student_id, request.challenge_id, campus_id
    )

    # 2. Get challenge context for theme
    challenge = None
    theme_name = session.theme_name
    if request.challenge_id:
        challenge = (
            db.query(Challenge).filter(Challenge.id == request.challenge_id).first()
        )
        if challenge:
            theme_name = challenge.theme_id  # Use theme_id from challenge

    # 3. Generate guide response using existing safety system
    persona = "Wellness Guide"  # Could be themed based on challenge
    reply = answer_message(
        message=request.message,
        guide=guide,
        settings=settings,
        persona=persona,
    )

    # 4. Store user message in database
    user_msg = ConversationMessage(
        session_id=session.id,
        role="user",
        content=request.message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)

    # 5. Store assistant response in database
    assistant_msg = ConversationMessage(
        session_id=session.id,
        role="assistant",
        content=reply.message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)

    # 6. Update session metadata
    session.message_count += 2  # User + assistant
    session.last_message_at = datetime.now(timezone.utc)
    if theme_name:
        session.theme_name = theme_name

    db.commit()

    # 7. Clean up old messages (privacy by design - FR-E6)
    _cleanup_old_messages(db, session.id)

    # 8. Get progress for nudges
    progress = None
    if request.challenge_id:
        progress = _get_student_progress(db, student_id, request.challenge_id)

    # 9. Return response
    return ConversationResponse(
        message=reply.message,
        next_task_nudge=None,  # Could add task nudges here
        theme_name=theme_name,
        progress=progress,
        session_id=session.id,
    )


@router.get("/history", response_model=list[ConversationHistoryResponse])
def get_conversation_history(
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[dict, Depends(get_current_student)],
):
    """Get the student's conversation sessions (US-16, FR-E6).

    Returns metadata about conversation sessions but respects privacy
    by only showing limited message history.
    """
    student_id = claims["student_id"]

    # Get recent conversation sessions
    sessions = (
        db.query(ConversationSession)
        .filter(ConversationSession.student_id == student_id)
        .order_by(ConversationSession.last_message_at.desc())
        .limit(10)
        .all()
    )

    result = []
    for session in sessions:
        # Get recent messages (limited)
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(10)
            .all()
        )

        result.append(
            ConversationHistoryResponse(
                session_id=session.id,
                theme_name=session.theme_name,
                message_count=session.message_count,
                messages=[
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                    }
                    for msg in reversed(messages)  # Oldest first
                ],
                created_at=session.created_at,
                last_message_at=session.last_message_at,
            )
        )

    return result


def _get_or_create_session(
    db: Session, student_id: int, challenge_id: int | None, campus_id: str
) -> ConversationSession:
    """Get or create an active conversation session (US-16).

    Sessions are scoped by student and optionally by challenge.
    If no recent session exists (< 1 hour old), create a new one.
    """
    # Look for a recent session (within 1 hour)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

    query = db.query(ConversationSession).filter(
        ConversationSession.student_id == student_id,
        ConversationSession.last_message_at >= cutoff,
    )

    if challenge_id:
        query = query.filter(ConversationSession.challenge_id == challenge_id)

    session = query.order_by(ConversationSession.last_message_at.desc()).first()

    if session:
        return session

    # Create a new session
    session = ConversationSession(
        student_id=student_id,
        challenge_id=challenge_id,
        theme_name=None,  # Will be set based on challenge
        message_count=0,
        created_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def _load_conversation_history(db: Session, session_id: int) -> list[dict]:
    """Load recent conversation messages for context (US-16, FR-E6).

    Limited to recent messages to respect privacy and token limits.
    Note: Currently not used but kept for future AI integration.
    """
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(20)  # Last 20 messages
        .all()
    )

    # Return in chronological order (oldest first)
    return [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(messages)
    ]


def _get_student_progress(db: Session, student_id: int, challenge_id: int) -> dict:
    """Calculate student's progress in a challenge."""
    # Count completed tasks
    completed_count = (
        db.query(func.count(CheckIn.id))
        .join(Task, CheckIn.task_id == Task.id)
        .filter(
            CheckIn.student_id == student_id,
            Task.challenge_id == challenge_id,
        )
        .scalar()
    )

    # Count total tasks
    total_count = (
        db.query(func.count(Task.id))
        .filter(Task.challenge_id == challenge_id)
        .scalar()
    )

    # Count required tasks remaining
    completed_task_ids = (
        db.query(CheckIn.task_id)
        .filter(CheckIn.student_id == student_id)
        .all()
    )
    completed_ids = [task_id for (task_id,) in completed_task_ids]

    remaining_required = (
        db.query(func.count(Task.id))
        .filter(
            Task.challenge_id == challenge_id,
            Task.is_required == True,
            Task.id.notin_(completed_ids) if completed_ids else True,
        )
        .scalar()
    )

    return {
        "completed_count": completed_count or 0,
        "total_count": total_count or 0,
        "remaining_required": remaining_required or 0,
        "is_prize_eligible": remaining_required == 0,
    }


def _cleanup_old_messages(db: Session, session_id: int) -> None:
    """Clean up old messages for privacy (FR-E6).

    Keeps only the most recent messages and deletes messages older than 24 hours.
    This implements minimal logging with no long-term PHI retention.
    """
    # Delete messages older than 24 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    db.query(ConversationMessage).filter(
        ConversationMessage.session_id == session_id,
        ConversationMessage.created_at < cutoff,
    ).delete()

    # Keep only the last 50 messages per session
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.desc())
        .offset(50)
        .all()
    )

    for msg in messages:
        db.delete(msg)

    db.commit()
