"""Executable Gherkin for FR-D6 — Manual completion override with audit (US-27).

Binds tests/features/manual_override.feature, which is a verbatim copy of the
scenarios in docs/features.md. This is the repo's first pytest-bdd module; the
plain-pytest edge cases live alongside it in test_manual_override.py.

One honest caveat: the second scenario's "When I remove or correct it" is an
either/or in a single step. pytest-bdd cannot branch, and the feature file is
doc-verbatim so a Scenario Outline is not available. This module implements the
*remove* half, which carries the sharper prior-state assertion; the *correct*
half is covered by test_manual_override.py::TestCorrectCheckIn.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.models.challenge import CheckIn

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/manual_override.feature")

ADMIN = "admin@csub.edu"
STUDENT = "student@csub.edu"
REASON = "Student attended but the scanner was down."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _ensure_task(client, context: dict, title: str) -> None:
    """Create the challenge + the named task, stashing their ids in context."""
    if "task_id" in context:
        return
    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
    ).json()
    context["challenge_id"] = challenge["id"]

    task = client.post(
        f"/api/challenges/{challenge['id']}/tasks",
        json={
            "title": title,
            "caption": "Learn what a balanced plate looks like.",
            "activity_type": "workshop",
            "location": "SHS Lobby",
            "required": True,
        },
    ).json()
    context["task_id"] = task["id"]


def _ensure_student(client, context: dict) -> None:
    """Mint the Student row via the IdP, then restore the admin session.

    Student rows only exist once a subject has signed in. Signing in as the
    student swaps the session cookie, so the admin must be restored or every
    subsequent admin call 403s.
    """
    if "student_signed_in" not in context:
        _sign_in_as(client, "student", STUDENT)
        context["student_signed_in"] = True
        _sign_in_as(client, "staff", ADMIN)


def _audits(client, context: dict) -> list[dict]:
    return client.get(
        f"/api/challenges/{context['challenge_id']}/tasks/{context['task_id']}/audits"
    ).json()


def _checkins(client, context: dict) -> list[dict]:
    return client.get(
        f"/api/challenges/{context['challenge_id']}/tasks/{context['task_id']}/checkins"
    ).json()


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("I am signed in as an admin")
def signed_in_as_admin(client, context):
    _sign_in_as(client, "staff", ADMIN)
    context["actor"] = ADMIN


# ---------------------------------------------------------------------------
# Scenario: Admin manually marks a completion
# ---------------------------------------------------------------------------


@when(parsers.parse('I manually mark a student complete for "{title}"'))
def manually_mark_complete(client, context, title):
    _ensure_task(client, context, title)
    _ensure_student(client, context)
    resp = client.post(
        f"/api/challenges/{context['challenge_id']}/tasks/{context['task_id']}/checkins",
        json={"student_subject": STUDENT, "reason": REASON},
    )
    assert resp.status_code == 201, resp.text
    context["resp"] = resp


@then(parsers.parse('a check-in is recorded with method "{method}"'))
def checkin_recorded_with_method(client, context, method):
    rows = _checkins(client, context)
    assert len(rows) == 1
    assert rows[0]["method"] == method
    assert rows[0]["student_subject"] == STUDENT
    # method="manual" alone does not prove an admin did it — a student's own
    # passport check-in writes "manual" too. verified_by is the distinguishing mark.
    assert rows[0]["verified_by"] == ADMIN


@then("the audit trail records my identity, the timestamp, and a reason")
def audit_records_who_when_why(client, context):
    audits = _audits(client, context)
    assert len(audits) == 1
    audit = audits[0]
    assert audit["action"] == "create"
    assert audit["actor_subject"] == context["actor"]  # who
    assert audit["ts"]  # when
    assert audit["reason"] == REASON  # why
    assert audit["prior_state"] is None  # nothing existed before
    assert audit["new_state"]["method"] == "manual"


# ---------------------------------------------------------------------------
# Scenario: Admin overrides an existing completion
# ---------------------------------------------------------------------------


@given(parsers.parse('a student has an erroneous completion for "{title}"'))
def erroneous_completion(client, db_sessionmaker, context, title):
    _ensure_task(client, context, title)
    _ensure_student(client, context)

    student_id = _lookup_student_id(db_sessionmaker, STUDENT)
    # Seeded straight through the ORM, not the API: going through the admin
    # endpoint would itself write a "create" audit row and pollute the counts
    # below. method="event_qr" makes the erroneous prior state distinguishable.
    with db_sessionmaker() as db:
        checkin = CheckIn(
            student_id=student_id,
            task_id=context["task_id"],
            ts=datetime(2025, 9, 8, 12, 0, tzinfo=timezone.utc),
            method="event_qr",
            verified_by=None,
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        context["checkin_id"] = checkin.id
        context["prior_method"] = checkin.method


def _lookup_student_id(db_sessionmaker, subject: str) -> int:
    from app.models.student import Student

    with db_sessionmaker() as db:
        student = db.query(Student).filter(Student.sso_subject == subject).one()
        return student.id


@when("I remove or correct it")
def remove_or_correct_it(client, context):
    # httpx has no client.delete(json=...) — the body must go through .request().
    resp = client.request(
        "DELETE",
        f"/api/challenges/{context['challenge_id']}/tasks/{context['task_id']}"
        f"/checkins/{context['checkin_id']}",
        json={"reason": REASON},
    )
    assert resp.status_code == 204, resp.text
    context["resp"] = resp


@then("the change is recorded in the audit trail")
def change_recorded_in_audit(client, context):
    audits = _audits(client, context)
    assert len(audits) == 1
    assert audits[0]["action"] == "delete"
    assert audits[0]["actor_subject"] == context["actor"]
    assert audits[0]["reason"] == REASON


@then("the prior state is preserved for audit")
def prior_state_preserved(client, context):
    prior = _audits(client, context)[0]["prior_state"]
    assert prior is not None
    assert prior["method"] == context["prior_method"]  # the erroneous "event_qr"
    assert prior["student_subject"] == STUDENT
    assert prior["checkin_id"] == context["checkin_id"]
    assert prior["ts"]
    # The CheckIn itself is gone — the snapshot is the only surviving record.
    assert _checkins(client, context) == []
