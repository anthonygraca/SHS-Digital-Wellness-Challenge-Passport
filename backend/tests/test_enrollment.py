"""US-3 / FR-C1 — Challenge enrollment.

Covers the three Gherkin scenarios (enroll → record created; cannot enroll twice;
no active challenge → friendly message, no enrollment) plus the inherited
eligibility guards (non-current student 403, unauthenticated 401).

Follows test_eligibility.py / test_challenges.py: mock IdP ACS sign-in holds the
session cookie, and challenges are inserted directly via the db_sessionmaker so
enrollment can be tested without the admin builder.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.challenge import Challenge, Enrollment


def _sign_in(client, affiliation: str = "student", subject: str = "abc@csub.edu"):
    """Sign in via the mock IdP ACS so the client holds the session cookie."""
    return client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _make_challenge(
    db_sessionmaker, campus_id: str = "csub", status: str = "published", **overrides
) -> int:
    """Insert a challenge directly and return its id."""
    db = db_sessionmaker()
    try:
        challenge = Challenge(
            campus_id=campus_id,
            name=overrides.get("name", "Stranger Things Challenge"),
            semester=overrides.get("semester", "Fall 2025"),
            start_date=overrides.get("start_date", date(2025, 9, 1)),
            end_date=overrides.get("end_date", date(2025, 12, 15)),
            status=status,
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)
        return challenge.id
    finally:
        db.close()


def _enrollment_count(db_sessionmaker) -> int:
    db = db_sessionmaker()
    try:
        return len(db.execute(select(Enrollment)).scalars().all())
    finally:
        db.close()


# --- Scenario 1: Student enrolls in the active challenge ------------------------


def test_current_student_enrolls_and_record_created(client, db_sessionmaker):
    challenge_id = _make_challenge(db_sessionmaker)
    _sign_in(client)

    resp = client.post("/enrollment")

    assert resp.status_code == 200
    body = resp.json()
    assert body["challenge_id"] == challenge_id
    assert body["enrolled_at"]
    assert _enrollment_count(db_sessionmaker) == 1


# --- Scenario 2: Student cannot enroll twice -----------------------------------


def test_enrolling_twice_is_idempotent(client, db_sessionmaker):
    _make_challenge(db_sessionmaker)
    _sign_in(client)

    first = client.post("/enrollment")
    second = client.post("/enrollment")

    assert first.status_code == 200
    assert second.status_code == 200
    # Same enrollment returned, and exactly one row exists.
    assert _enrollment_count(db_sessionmaker) == 1


def test_status_reflects_already_enrolled(client, db_sessionmaker):
    _make_challenge(db_sessionmaker)
    _sign_in(client)

    before = client.get("/enrollment").json()
    assert before["enrolled"] is False
    assert before["active_challenge"]["name"] == "Stranger Things Challenge"

    client.post("/enrollment")

    after = client.get("/enrollment").json()
    assert after["enrolled"] is True


# --- Scenario 3: No active challenge for the campus -----------------------------


def test_post_without_active_challenge_is_404_with_message(client, db_sessionmaker):
    _sign_in(client)
    resp = client.post("/enrollment")

    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "no_active_challenge"
    assert detail["message"]
    assert _enrollment_count(db_sessionmaker) == 0


def test_status_without_active_challenge_returns_null(client):
    _sign_in(client)
    resp = client.get("/enrollment")

    assert resp.status_code == 200
    body = resp.json()
    assert body["active_challenge"] is None
    assert body["enrolled"] is False


def test_draft_challenge_is_not_joinable(client, db_sessionmaker):
    """Only published challenges are joinable — a draft looks like no challenge."""
    _make_challenge(db_sessionmaker, status="draft")
    _sign_in(client)

    assert client.get("/enrollment").json()["active_challenge"] is None
    assert client.post("/enrollment").status_code == 404


# --- Inherited eligibility guards ----------------------------------------------


def test_non_current_student_is_blocked(client, db_sessionmaker):
    _make_challenge(db_sessionmaker)
    _sign_in(client, affiliation="alum")

    resp = client.post("/enrollment")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "not_current_student"
    assert _enrollment_count(db_sessionmaker) == 0


def test_unauthenticated_cannot_enroll(client):
    assert client.post("/enrollment").status_code == 401
    assert client.get("/enrollment").status_code == 401
