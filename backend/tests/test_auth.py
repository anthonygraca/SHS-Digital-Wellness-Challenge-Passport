from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.models.student import Student
from app.services.students import get_or_create_student


def _all_students(db_sessionmaker):
    with db_sessionmaker() as db:
        return list(db.execute(select(Student)).scalars())


def _acs(client, **fields):
    """POST an 'assertion' to the ACS without following the redirect."""
    fields.setdefault("returnTo", "/app")
    return client.post("/auth/acs", data=fields, follow_redirects=False)


# --- US-1 Gherkin scenario 1: first-time student authenticates -----------------


def test_first_time_creates_minimal_record(client, db_sessionmaker):
    resp = _acs(client, subject="abc@csub.edu", affiliation="student")

    assert resp.status_code == 302
    assert "status=failed" not in resp.headers["location"]
    assert get_settings().session_cookie in resp.cookies

    students = _all_students(db_sessionmaker)
    assert len(students) == 1
    s = students[0]
    assert s.sso_subject == "abc@csub.edu"
    assert s.affiliation == "student"
    assert s.campus_id == "csub"  # derived from the mock issuer


def test_student_table_stores_only_opaque_identity(db_sessionmaker):
    # FR-A2 enforced at the schema: no name, no 9-digit ID, no password columns.
    # FR-A4: role column added for access control (US-4)
    columns = set(Student.__table__.columns.keys())
    assert columns == {"id", "campus_id", "sso_subject", "affiliation", "role", "created_at"}
    forbidden = {"name", "password", "student_id_number", "ssn", "dob"}
    assert columns.isdisjoint(forbidden)


# --- US-1 Gherkin scenario 2: returning student is loaded, not duplicated -------


def test_returning_student_not_duplicated(client, db_sessionmaker):
    first = _acs(client, subject="abc@csub.edu", affiliation="student")
    second = _acs(client, subject="abc@csub.edu", affiliation="student")

    assert first.status_code == 302 and second.status_code == 302
    students = _all_students(db_sessionmaker)
    assert len(students) == 1


# --- US-1 Gherkin scenario 3: failed authentication creates no record -----------


def test_failed_assertion_creates_no_record(client, db_sessionmaker):
    resp = _acs(client, subject="abc@csub.edu", fail="1")

    assert resp.status_code == 302
    assert "status=failed" in resp.headers["location"]
    assert get_settings().session_cookie not in resp.cookies
    assert _all_students(db_sessionmaker) == []


def test_missing_subject_creates_no_record(client, db_sessionmaker):
    resp = _acs(client, subject="")

    assert resp.status_code == 302
    assert "status=failed" in resp.headers["location"]
    assert _all_students(db_sessionmaker) == []


# --- get_or_create unit + session endpoint --------------------------------------


def test_get_or_create_is_idempotent(db_sessionmaker):
    with db_sessionmaker() as db:
        s1, created1 = get_or_create_student(db, "csub", "abc@csub.edu", "student")
        s2, created2 = get_or_create_student(db, "csub", "abc@csub.edu", "student")
        assert created1 is True and created2 is False
        assert s1.id == s2.id


def test_session_requires_auth_then_returns_identity(client):
    assert client.get("/auth/session").status_code == 401

    # Sign in (follow the ACS redirect); the client keeps the session cookie.
    client.post(
        "/auth/acs",
        data={"subject": "abc@csub.edu", "affiliation": "student", "returnTo": "/app"},
    )
    me = client.get("/auth/session")
    assert me.status_code == 200
    body = me.json()
    # US-4 adds role and student_id to session response
    assert body == {
        "subject": "abc@csub.edu",
        "affiliation": "student",
        "isCurrentStudent": True,
        "role": "student",
        "student_id": 1,
    }
