"""Tests for check-in endpoints and personalized tips (US-15, FR-D1, FR-E1, FR-E6)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Challenge, CheckIn, Enrollment, Task
from app.models.challenge import ActivityType, ChallengeStatus, CheckInMethod
from app.services.ai_tips import AITipsService


def _create_test_challenge(db_session, campus_id="csub"):
    """Helper to create a test challenge with tasks."""
    now = datetime.now(timezone.utc)
    challenge = Challenge(
        campus_id=campus_id,
        name="Digital Wellness Challenge",
        semester="Fall 2026",
        status=ChallengeStatus.ACTIVE.value,
        starts_on=now - timedelta(days=7),
        ends_on=now + timedelta(days=30),
    )
    db_session.add(challenge)
    db_session.flush()

    # Add tasks
    task1 = Task(
        challenge_id=challenge.id,
        week_no=1,
        title="Vision Health Check",
        caption="Get your eyes checked and learn about screen health",
        activity_type=ActivityType.SCREENING.value,
        location="Student Health Services",
        date_start=now - timedelta(days=5),
        date_end=now + timedelta(days=10),
        is_required=True,
        order=1,
        content_tags="vision, preventive care",
    )
    task2 = Task(
        challenge_id=challenge.id,
        week_no=2,
        title="Nutrition Workshop",
        caption="Learn about balanced meals and campus dining",
        activity_type=ActivityType.WORKSHOP.value,
        location="Rec Center",
        date_start=now - timedelta(days=3),
        date_end=now + timedelta(days=15),
        is_required=True,
        order=2,
        content_tags="nutrition, wellness",
    )
    task3 = Task(
        challenge_id=challenge.id,
        week_no=3,
        title="Mindfulness Session",
        caption="Optional meditation and stress management",
        activity_type=ActivityType.WORKSHOP.value,
        location="Campus Center",
        date_start=now - timedelta(days=1),
        date_end=now + timedelta(days=20),
        is_required=False,
        order=3,
        content_tags="mental health, mindfulness",
    )
    db_session.add_all([task1, task2, task3])
    db_session.commit()
    return challenge, [task1, task2, task3]


def _enroll_student(db_session, student_id, challenge_id):
    """Helper to enroll a student in a challenge."""
    enrollment = Enrollment(student_id=student_id, challenge_id=challenge_id)
    db_session.add(enrollment)
    db_session.commit()
    return enrollment


def _sign_in_student(client, subject="test@csub.edu", affiliation="student"):
    """Helper to sign in a student and return the session."""
    resp = client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    return resp


# --- US-15 Gherkin Scenario 1: Tip is shown after a check-in -------------------


def test_checkin_returns_personalized_tip(client, db_sessionmaker):
    """Test that checking in to a task returns a personalized tip (US-15)."""
    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)
        task = tasks[0]  # Vision Health Check

    # Sign in and enroll
    _sign_in_student(client)
    session_resp = client.get("/auth/session")
    student_id = session_resp.json().get("student_id")

    with db_sessionmaker() as db:
        _enroll_student(db, student_id, challenge.id)

    # Check in to the task
    resp = client.post(
        "/api/checkins/",
        json={"task_id": task.id, "method": "event_qr"},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Verify the response structure (US-15)
    assert "checkin_id" in data
    assert data["task_title"] == "Vision Health Check"
    assert "checked_in_at" in data
    assert "personalized_tip" in data

    # Verify personalized tip contains required fields (FR-E1)
    tip = data["personalized_tip"]
    assert "tip" in tip
    assert "resource" in tip
    assert "next_step" in tip
    assert len(tip["tip"]) > 10  # Should be a meaningful tip

    # Verify progress is included
    assert "progress" in data
    progress = data["progress"]
    assert progress["completed_tasks"] == 1
    assert progress["total_tasks"] == 3


# --- US-15 Gherkin Scenario 2: Tip is personalized by progress -----------------


def test_tip_acknowledges_remaining_progress(client, db_sessionmaker):
    """Test that tips acknowledge remaining required tasks (US-15)."""
    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)

    # Sign in and enroll
    _sign_in_student(client)
    session_resp = client.get("/auth/session")
    student_id = session_resp.json().get("student_id")

    with db_sessionmaker() as db:
        _enroll_student(db, student_id, challenge.id)

    # Check in to first required task
    resp = client.post(
        "/api/checkins/",
        json={"task_id": tasks[0].id, "method": "event_qr"},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Verify progress shows remaining required tasks
    progress = data["progress"]
    assert progress["remaining_required_tasks"] == 1  # One more required task
    assert progress["is_prize_eligible"] is False

    # Check in to second required task
    resp2 = client.post(
        "/api/checkins/",
        json={"task_id": tasks[1].id, "method": "event_qr"},
    )

    assert resp2.status_code == 200
    data2 = resp2.json()

    # Now should be prize eligible
    progress2 = data2["progress"]
    assert progress2["remaining_required_tasks"] == 0
    assert progress2["is_prize_eligible"] is True


# --- US-15 Gherkin Scenario 3: Model calls are server-side with no PHI ---------


def test_ai_tips_service_no_phi_in_prompt(db_sessionmaker):
    """Test that AI tips service doesn't include PHI in prompts (FR-E6)."""
    from app.config import get_settings

    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)
        task = tasks[0]

    settings = get_settings()
    ai_service = AITipsService(settings)

    # Build a prompt (without actually calling Bedrock)
    prompt = ai_service._build_tip_prompt(
        task=task,
        remaining_required_tasks=1,
        completed_count=1,
        total_count=3,
    )

    # Verify no PHI is in the prompt
    # PHI would include: student names, IDs, SSN, DOB, etc.
    assert "student_id" not in prompt.lower()
    assert "@csub.edu" not in prompt  # No SSO subject
    assert "abc" not in prompt.lower()  # No identifiers
    assert "sso" not in prompt.lower()

    # Verify grounded content is present
    assert "SHS" in prompt or "Student Health Services" in prompt
    assert task.title in prompt
    assert task.activity_type in prompt


# --- Additional test cases ------------------------------------------------------


def test_checkin_requires_enrollment(client, db_sessionmaker):
    """Test that students must be enrolled before checking in (FR-D1)."""
    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)

    # Sign in but don't enroll
    _sign_in_student(client)

    # Try to check in without enrollment
    resp = client.post(
        "/api/checkins/",
        json={"task_id": tasks[0].id, "method": "event_qr"},
    )

    assert resp.status_code == 403
    assert "enrolled" in resp.json()["detail"].lower()


def test_checkin_validates_date_window(client, db_sessionmaker):
    """Test that check-ins are only allowed within the task date window (FR-D1)."""
    with db_sessionmaker() as db:
        now = datetime.now(timezone.utc)
        challenge = Challenge(
            campus_id="csub",
            name="Test Challenge",
            semester="Fall 2026",
            status=ChallengeStatus.ACTIVE.value,
            starts_on=now - timedelta(days=7),
            ends_on=now + timedelta(days=30),
        )
        db.add(challenge)
        db.flush()

        # Task in the future
        future_task = Task(
            challenge_id=challenge.id,
            week_no=1,
            title="Future Task",
            activity_type=ActivityType.WORKSHOP.value,
            date_start=now + timedelta(days=5),
            date_end=now + timedelta(days=10),
            is_required=True,
            order=1,
        )
        db.add(future_task)
        db.commit()

    # Sign in and enroll
    _sign_in_student(client)
    session_resp = client.get("/auth/session")
    student_id = session_resp.json().get("student_id")

    with db_sessionmaker() as db:
        _enroll_student(db, student_id, challenge.id)

    # Try to check in to future task
    resp = client.post(
        "/api/checkins/",
        json={"task_id": future_task.id, "method": "event_qr"},
    )

    assert resp.status_code == 400
    assert "available" in resp.json()["detail"].lower()


def test_checkin_is_idempotent(client, db_sessionmaker):
    """Test that duplicate check-ins don't create multiple records."""
    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)

    # Sign in and enroll
    _sign_in_student(client)
    session_resp = client.get("/auth/session")
    student_id = session_resp.json().get("student_id")

    with db_sessionmaker() as db:
        _enroll_student(db, student_id, challenge.id)

    # Check in twice
    resp1 = client.post(
        "/api/checkins/",
        json={"task_id": tasks[0].id, "method": "event_qr"},
    )
    resp2 = client.post(
        "/api/checkins/",
        json={"task_id": tasks[0].id, "method": "event_qr"},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    # Verify only one check-in record exists
    with db_sessionmaker() as db:
        checkins = db.query(CheckIn).filter(CheckIn.student_id == student_id).all()
        assert len(checkins) == 1


def test_get_progress_endpoint(client, db_sessionmaker):
    """Test the progress endpoint returns correct metrics."""
    with db_sessionmaker() as db:
        challenge, tasks = _create_test_challenge(db)

    # Sign in and enroll
    _sign_in_student(client)
    session_resp = client.get("/auth/session")
    student_id = session_resp.json().get("student_id")

    with db_sessionmaker() as db:
        _enroll_student(db, student_id, challenge.id)

    # Get initial progress
    resp = client.get(f"/api/checkins/progress/{challenge.id}")
    assert resp.status_code == 200
    progress = resp.json()

    assert progress["completed_tasks"] == 0
    assert progress["total_tasks"] == 3
    assert progress["required_tasks"] == 2
    assert progress["remaining_required_tasks"] == 2
    assert progress["is_prize_eligible"] is False


def test_ai_tips_fallback_when_bedrock_unavailable():
    """Test that fallback tips are returned when Bedrock is unavailable (US-15)."""
    from app.config import Settings
    from app.models import Task

    # Create a settings object with AI tips disabled
    settings = Settings(ai_tips_enabled=False)
    ai_service = AITipsService(settings)

    # Create a mock task
    task = Task(
        id=1,
        challenge_id=1,
        week_no=1,
        title="Vision Health Check",
        activity_type=ActivityType.SCREENING.value,
        content_tags="vision",
        date_start=datetime.now(timezone.utc),
        date_end=datetime.now(timezone.utc) + timedelta(days=7),
        is_required=True,
        order=1,
    )

    # Generate tip (should use fallback)
    tip = ai_service.generate_tip(
        task=task,
        remaining_required_tasks=1,
        completed_count=1,
        total_count=3,
    )

    # Verify fallback tip structure
    assert tip.tip is not None
    assert tip.resource is not None
    assert tip.next_step is not None
    assert len(tip.tip) > 20  # Should be a meaningful tip
    assert "vision" in tip.tip.lower() or "eye" in tip.tip.lower()
