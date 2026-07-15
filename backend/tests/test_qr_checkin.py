from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.challenge import Challenge, CheckIn, Task
from app.models.student import Student
from app.services.qr import mint_event_token
from app.services.seed import seed_demo_challenge


def _seed_challenge(db_sessionmaker):
    with db_sessionmaker() as db:
        seed_demo_challenge(db)


def _sign_in(client, subject="abc@csub.edu", affiliation="student"):
    """Sign in through the mock IdP so the client carries the session cookie."""
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _task_ids_by_week(db_sessionmaker):
    with db_sessionmaker() as db:
        tasks = db.execute(select(Task).order_by(Task.position)).scalars()
        return {t.position: t.id for t in tasks}


def _checkins(db_sessionmaker):
    with db_sessionmaker() as db:
        return list(db.execute(select(CheckIn)).scalars())


# --- Successful check-in marks the week complete (US-8 scenario 1) ---------------


def test_scan_marks_week_complete_and_returns_tip(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    token = mint_event_token(_task_ids_by_week(db_sessionmaker)[3])

    resp = client.post("/api/checkins/scan", json={"token": token})
    assert resp.status_code == 200
    body = resp.json()

    # The week that was scanned flips to complete and the countdown updates.
    assert body["weekNo"] == 3
    assert body["passport"]["completedWeeks"] == 1
    assert body["passport"]["remainingWeeks"] == 6
    assert body["passport"]["weeks"][2]["status"] == "complete"

    # A personalized tip naming the task is shown (FR-E1).
    assert body["title"] in body["tip"]
    assert body["tip"]

    # Exactly one check-in, recorded with method event_qr and a timestamp.
    rows = _checkins(db_sessionmaker)
    assert len(rows) == 1
    assert rows[0].method == "event_qr"
    assert rows[0].ts is not None


# --- Duplicate scan is rejected (US-8 scenario 2) --------------------------------


def test_scan_duplicate_is_rejected(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    token = mint_event_token(_task_ids_by_week(db_sessionmaker)[3])

    assert client.post("/api/checkins/scan", json={"token": token}).status_code == 200
    resp = client.post("/api/checkins/scan", json={"token": token})

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Already completed this week"
    # No second check-in recorded.
    assert len(_checkins(db_sessionmaker)) == 1


# --- Expired or invalid token is rejected (US-8 scenario 3) ----------------------


def test_scan_invalid_token_is_rejected(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    resp = client.post("/api/checkins/scan", json={"token": "not-a-real-token"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This code is no longer valid, ask the attendant"
    assert _checkins(db_sessionmaker) == []


def test_scan_tampered_token_is_rejected(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    token = mint_event_token(_task_ids_by_week(db_sessionmaker)[1])
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")

    resp = client.post("/api/checkins/scan", json={"token": tampered})
    assert resp.status_code == 400
    assert _checkins(db_sessionmaker) == []


def test_scan_token_for_foreign_challenge_is_rejected(client, db_sessionmaker):
    """A signed token whose task is not in this campus's active challenge is invalid."""
    _seed_challenge(db_sessionmaker)
    _sign_in(client)  # signs in on campus "csub"

    with db_sessionmaker() as db:
        other = Challenge(
            campus_id="other",
            name="Other Campus Challenge",
            semester="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 10, 1),
            status="published",
        )
        db.add(other)
        db.flush()
        foreign_task = Task(challenge_id=other.id, position=1, title="Foreign Week")
        db.add(foreign_task)
        db.commit()
        foreign_token = mint_event_token(foreign_task.id)

    resp = client.post("/api/checkins/scan", json={"token": foreign_token})
    assert resp.status_code == 400
    # The csub student recorded nothing.
    with db_sessionmaker() as db:
        csub_students = db.execute(
            select(Student).where(Student.campus_id == "csub")
        ).scalars()
        ids = [s.id for s in csub_students]
    assert all(row.student_id not in ids for row in _checkins(db_sessionmaker))


# --- Ineligible student cannot check in (US-8 scenario 5) ------------------------


def test_scan_403_for_non_current_student(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    token = mint_event_token(_task_ids_by_week(db_sessionmaker)[1])
    _sign_in(client, subject="alum@csub.edu", affiliation="alum")

    resp = client.post("/api/checkins/scan", json={"token": token})
    assert resp.status_code == 403
    # The gate runs before the service, so nothing is recorded.
    assert _checkins(db_sessionmaker) == []


def test_scan_requires_auth(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    token = mint_event_token(_task_ids_by_week(db_sessionmaker)[1])
    assert client.post("/api/checkins/scan", json={"token": token}).status_code == 401
