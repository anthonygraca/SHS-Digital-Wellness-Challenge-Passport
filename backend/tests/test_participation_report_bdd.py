"""Executable Gherkin for FR-F1 — Participation & completion funnel report (US-21).

Binds tests/features/participation_report.feature, a verbatim copy of the scenarios
in docs/features.md. The plain-pytest edge cases — RBAC, no-active-challenge,
campus isolation, empty funnels — live in test_participation_report.py.

Two notes on binding these scenarios:

"And the weeks are shown as a funnel" is a claim about the *API*, not about bars on
a screen: what the endpoint owes a funnel renderer is every week of the challenge,
each with its count, in week order. The rendering itself is Reports.test.tsx's job.

"Then week 4's completion count increases by one" needs a before-value to increase
from, so the Given step fetches the report once to bank the baseline before
recording the new check-in.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/participation_report.feature")

ADMIN = "admin@csub.edu"
WEEKS = 4
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu", "s4@csub.edu"]

# A deliberately funnel-shaped cohort: everyone finishes week 1, one fewer each
# week after. Indexed by week number.
COMPLETIONS = {1: STUDENTS[:4], 2: STUDENTS[:3], 3: STUDENTS[:2], 4: STUDENTS[:1]}

# Week 4's newcomer in scenario 2 — the first student not already counted there.
NEW_CHECKIN_STUDENT = STUDENTS[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _record_checkin(client, context: dict, week_no: int, subject: str) -> None:
    """Mark a student complete for a week, as the admin. Assumes an admin session."""
    resp = client.post(
        f"/api/challenges/{context['challenge_id']}/tasks/{context['task_ids'][week_no]}"
        "/checkins",
        json={"student_subject": subject, "reason": "Attended in person"},
    )
    assert resp.status_code == 201, resp.text


def _fetch_report(client) -> dict:
    resp = client.get("/api/reports/participation")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _week(report: dict, week_no: int) -> dict:
    return next(w for w in report["weeks"] if w["week_no"] == week_no)


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("I am signed in as an admin viewing the active challenge")
def signed_in_as_admin_with_an_active_challenge(client, context):
    """A published 4-week challenge, four enrolled students, and a funnel of check-ins.

    Ends on an admin session, which is the state the scenarios start from.
    """
    _sign_in_as(client, "staff", ADMIN)
    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 - Stranger Things",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
            "theme_id": "stranger-things",
        },
    ).json()
    context["challenge_id"] = challenge["id"]

    context["task_ids"] = {}
    for week_no in range(1, WEEKS + 1):
        task = client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": f"Week {week_no}", "required": True},
        ).json()
        context["task_ids"][week_no] = task["id"]

    client.post(f"/api/challenges/{challenge['id']}/publish")

    # Enrolling mints the Student rows the check-ins below address by subject.
    for subject in STUDENTS:
        _sign_in_as(client, "student", subject)
        assert client.post("/enrollment").status_code == 200

    _sign_in_as(client, "staff", ADMIN)
    for week_no, subjects in COMPLETIONS.items():
        for subject in subjects:
            _record_checkin(client, context, week_no, subject)


# ---------------------------------------------------------------------------
# Scenario: Report shows enrollment and per-week completion
# ---------------------------------------------------------------------------


@when("I open the participation report")
def i_open_the_participation_report(client, context):
    context["report"] = _fetch_report(client)


@then("I see total enrollments")
def i_see_total_enrollments(context):
    assert context["report"]["total_enrollments"] == len(STUDENTS)


@then("I see the count of students completing each week")
def i_see_per_week_completion_counts(context):
    counts = {w["week_no"]: w["completed_count"] for w in context["report"]["weeks"]}
    assert counts == {wk: len(subs) for wk, subs in COMPLETIONS.items()}


@then("the weeks are shown as a funnel")
def the_weeks_are_shown_as_a_funnel(context):
    weeks = context["report"]["weeks"]
    # Every week of the challenge, in week order — what a funnel renderer needs
    # to draw the drop-off from one rung to the next.
    assert [w["week_no"] for w in weeks] == list(range(1, WEEKS + 1))
    counts = [w["completed_count"] for w in weeks]
    assert counts == sorted(counts, reverse=True), "the seeded cohort tapers by week"


# ---------------------------------------------------------------------------
# Scenario: Report reflects new check-ins
# ---------------------------------------------------------------------------


@given("a new check-in is recorded for week 4")
def a_new_checkin_is_recorded_for_week_4(client, context):
    context["before"] = _fetch_report(client)
    _record_checkin(client, context, 4, NEW_CHECKIN_STUDENT)


@when("I refresh the report")
def i_refresh_the_report(client, context):
    context["report"] = _fetch_report(client)


@then("week 4's completion count increases by one")
def week_4_count_increases_by_one(context):
    before, after = context["before"], context["report"]
    assert _week(after, 4)["completed_count"] == _week(before, 4)["completed_count"] + 1

    # The other rungs are untouched — a check-in completes one week, not the run.
    for week_no in (1, 2, 3):
        assert (
            _week(after, week_no)["completed_count"]
            == _week(before, week_no)["completed_count"]
        )
    assert after["total_enrollments"] == before["total_enrollments"]
