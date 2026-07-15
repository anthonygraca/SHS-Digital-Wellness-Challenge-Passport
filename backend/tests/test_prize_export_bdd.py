"""Executable Gherkin for FR-F5 — Prize-eligible CSV export (US-26).

Binds tests/features/prize_export.feature, a verbatim copy of the scenarios in
docs/features.md. The plain-pytest edge cases — RBAC, no-active-challenge, campus
isolation, the all-optional challenge, the empty file — live in test_prize_export.py.

Two notes on binding these scenarios:

"Given several students, some with all required tasks complete" is seeded with a
cohort that separates the two rules the export has to get right at once: ELIGIBLE
holds a student who did only the required tasks and one who also did the optional
one, INELIGIBLE holds a student missing a single required task and one who did the
optional task *only*. If the query confused "all tasks" with "all required tasks",
one of those four would land on the wrong side.

"When I re-export the list" needs a first export to re-export against, so the Given
in scenario 2 exports once — and asserts the student is absent — before recording
the final check-in. That absent-then-present pair is the whole claim of the
scenario: eligibility is derived per export, not stored at check-in time.
"""

from __future__ import annotations

import csv
import io

import pytest
from pytest_bdd import given, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/prize_export.feature")

ADMIN = "admin@csub.edu"

# Weeks 1-3 are required, week 4 is optional — the distinction the export turns on.
REQUIRED_WEEKS = [1, 2, 3]
OPTIONAL_WEEK = 4

# Indexed by subject: the weeks that student has completed.
COMPLETIONS = {
    "all-required@csub.edu": [1, 2, 3],  # exactly the required set
    "everything@csub.edu": [1, 2, 3, 4],  # required set plus the optional week
    "missing-one@csub.edu": [1, 2],  # one required week short
    "optional-only@csub.edu": [4],  # did a week, but none of the required ones
}
STUDENTS = list(COMPLETIONS)
ELIGIBLE = ["all-required@csub.edu", "everything@csub.edu"]
INELIGIBLE = ["missing-one@csub.edu", "optional-only@csub.edu"]

# Scenario 2's newcomer: the student one required week short, and the week they owe.
NEWLY_ELIGIBLE = "missing-one@csub.edu"
FINAL_REQUIRED_WEEK = 3


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


def _export(client) -> list[dict]:
    """The exported CSV, parsed into rows. Assumes an admin session."""
    resp = client.get("/api/reports/prize-eligible.csv")
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


def _subjects(rows: list[dict]) -> set[str]:
    return {row["sso_subject"] for row in rows}


def _seed_cohort(client, context: dict) -> None:
    """A published challenge with 3 required weeks + 1 optional, and the COMPLETIONS.

    Ends on an admin session, which is the state the export steps need.
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
    for week_no in [*REQUIRED_WEEKS, OPTIONAL_WEEK]:
        task = client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={
                "title": f"Week {week_no}",
                "required": week_no in REQUIRED_WEEKS,
            },
        ).json()
        context["task_ids"][week_no] = task["id"]

    client.post(f"/api/challenges/{challenge['id']}/publish")

    # Enrolling mints the Student rows the check-ins below address by subject.
    for subject in STUDENTS:
        _sign_in_as(client, "student", subject)
        assert client.post("/enrollment").status_code == 200

    _sign_in_as(client, "staff", ADMIN)
    for subject, weeks in COMPLETIONS.items():
        for week_no in weeks:
            _record_checkin(client, context, week_no, subject)


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


# ---------------------------------------------------------------------------
# Scenario: Export contains only prize-eligible students
# ---------------------------------------------------------------------------


@given("several students, some with all required tasks complete")
def several_students_some_complete(client, context):
    _seed_cohort(client, context)


@when("I export the prize-eligible list")
def i_export_the_prize_eligible_list(client, context):
    context["rows"] = _export(client)


@then("the CSV contains only students who completed every required task")
def csv_contains_only_eligible_students(context):
    assert _subjects(context["rows"]) == set(ELIGIBLE)

    # Every exported row says *why* it qualified, and the two numbers agree.
    for row in context["rows"]:
        assert row["required_total"] == str(len(REQUIRED_WEEKS))
        assert row["required_completed"] == row["required_total"]


@then("students missing any required task are excluded")
def students_missing_a_required_task_are_excluded(context):
    subjects = _subjects(context["rows"])
    for subject in INELIGIBLE:
        assert subject not in subjects


# ---------------------------------------------------------------------------
# Scenario: Export reflects derived eligibility
# ---------------------------------------------------------------------------


@given("a student just completed their final required task")
def a_student_just_completed_their_final_required_task(client, context):
    _seed_cohort(client, context)

    # The first export is what makes the next one a *re*-export: it pins the
    # student as absent before the check-in that should let them in.
    assert NEWLY_ELIGIBLE not in _subjects(_export(client))

    _record_checkin(client, context, FINAL_REQUIRED_WEEK, NEWLY_ELIGIBLE)


@when("I re-export the list")
def i_re_export_the_list(client, context):
    context["rows"] = _export(client)


@then("that student now appears in the CSV")
def that_student_now_appears_in_the_csv(context):
    assert NEWLY_ELIGIBLE in _subjects(context["rows"])

    # Nothing was stored at check-in time: the row is derived, so it carries the
    # same complete required count as everyone else's.
    row = next(r for r in context["rows"] if r["sso_subject"] == NEWLY_ELIGIBLE)
    assert row["required_completed"] == str(len(REQUIRED_WEEKS))
    assert row["eligible_since"], "the moment the last required task landed"
