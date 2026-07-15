"""Executable Gherkin for FR-F2 — Auto-vs-manual attendance report (US-22).

Binds tests/features/attendance_report.feature, a verbatim copy of the scenarios in
docs/features.md. The plain-pytest edge cases — RBAC, no-active-challenge, campus
isolation, empty shapes — live in test_attendance_report.py.

Three notes on binding these scenarios:

Unlike US-21's feature file, this one has no Background — scenario 1 opens on a
`When`. Same world, different door: the challenge, the cohort and the mixed-method
check-ins are built by an autouse fixture instead of a @given. The doc is the
contract, so a Background cannot simply be added to make the seam prettier.

"Given most check-ins used event_qr" therefore does not seed — the fixture's cohort
is already majority-automatic. The step fetches and *pins* that as a precondition, so
scenario 2 reads against the same cohort scenario 1 counted.

"Then the automatically-captured share is shown as a percentage" is a claim about the
*API*, not about pixels — the same reading US-21 gave "the weeks are shown as a
funnel". Percentages are the client's job, so what the endpoint owes a renderer is a
share that is *computable*: an event_qr count and a non-zero total to divide it by.
The rendered "71%" is Reports.test.tsx's job.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from app.services.qr import mint_event_token

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/attendance_report.feature")

ADMIN = "admin@csub.edu"
WEEKS = 4
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu", "s4@csub.edu"]

# A deliberately majority-automatic cohort, seeded through the only two methods any
# write path can actually mint. Disjoint by (student, week) —
# uq_checkin_student_task would reject an overlap.
QR_CHECKINS = {STUDENTS[0]: [1, 2, 3], STUDENTS[1]: [1, 2]}
MANUAL_CHECKINS = {STUDENTS[2]: [1], STUDENTS[3]: [1]}

AUTO_COUNT = sum(len(weeks) for weeks in QR_CHECKINS.values())  # 5
MANUAL_COUNT = sum(len(weeks) for weeks in MANUAL_CHECKINS.values())  # 2
TOTAL = AUTO_COUNT + MANUAL_COUNT  # 7
AUTO_SHARE_PCT = 71  # round(5 / 7 * 100)


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


def _scan(client, context: dict, week_no: int, subject: str) -> None:
    """Record an event_qr check-in the only way one is ever made: a student scan.

    Signing in as the student and posting a minted token, rather than writing the
    row directly, is what makes this an *attendance capture* the report counts and
    not just a fixture that happens to say "event_qr".
    """
    _sign_in_as(client, "student", subject)
    token = mint_event_token(context["task_ids"][week_no])
    resp = client.post("/api/checkins/scan", json={"token": token})
    assert resp.status_code == 200, resp.text


def _fetch_report(client) -> dict:
    resp = client.get("/api/reports/attendance")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _count(report: dict, method: str) -> int:
    return next(m["count"] for m in report["methods"] if m["method"] == method)


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


@pytest.fixture(autouse=True)
def seeded(client, context):
    """A published 4-week challenge with a majority-automatic mix of check-ins.

    An autouse fixture rather than a @given because this feature file has no
    Background — see the module docstring. Ends on an admin session, which is the
    state both scenarios open in.
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

    # Enrolling mints the Student rows the manual check-ins below address by
    # subject. The scan path needs them too — it resolves the current student.
    for subject in STUDENTS:
        _sign_in_as(client, "student", subject)
        assert client.post("/enrollment").status_code == 200

    for subject, weeks in QR_CHECKINS.items():
        for week_no in weeks:
            _scan(client, context, week_no, subject)

    _sign_in_as(client, "staff", ADMIN)
    for subject, weeks in MANUAL_CHECKINS.items():
        for week_no in weeks:
            _record_checkin(client, context, week_no, subject)

    # No staff check-ins seeded: nothing in the app writes that method. The report
    # shows the bucket at 0 anyway, which is the finding, not an omission.


# ---------------------------------------------------------------------------
# Scenario: Attendance is broken down by method
# ---------------------------------------------------------------------------


@when("I open the attendance report")
def i_open_the_attendance_report(client, context):
    context["report"] = _fetch_report(client)


@then("I see counts grouped by method: event_qr, staff, and manual")
def i_see_counts_grouped_by_method(context):
    counts = {m["method"]: m["count"] for m in context["report"]["methods"]}
    # All three, always, in a fixed order — a bucket that vanished when nobody used
    # it would make "staff: 0" indistinguishable from "staff: not reported".
    assert list(counts) == ["event_qr", "staff", "manual"]
    assert counts == {"event_qr": AUTO_COUNT, "staff": 0, "manual": MANUAL_COUNT}


@then("the totals reconcile with total check-ins")
def the_totals_reconcile_with_total_checkins(context):
    report = context["report"]
    assert sum(m["count"] for m in report["methods"]) == report["total_checkins"]
    # And the total is the number of check-ins that actually exist — internal
    # consistency alone is vacuous, since 0 == 0 would satisfy the line above.
    assert report["total_checkins"] == TOTAL


# ---------------------------------------------------------------------------
# Scenario: Auto share is highlighted
# ---------------------------------------------------------------------------


@given("most check-ins used event_qr")
def most_checkins_used_event_qr(client):
    # Pinned, not seeded: the fixture's cohort is already majority-automatic, and
    # re-seeding here would make scenario 2 count a different world to scenario 1.
    report = _fetch_report(client)
    assert _count(report, "event_qr") * 2 > report["total_checkins"]


@when("I view the report")
def i_view_the_report(client, context):
    context["report"] = _fetch_report(client)


@then("the automatically-captured share is shown as a percentage")
def the_auto_share_is_shown_as_a_percentage(context):
    report = context["report"]
    # See the module docstring: what the API owes a renderer is a *computable*
    # share — a count, and a denominator that is not zero.
    assert report["total_checkins"] > 0
    share = round(_count(report, "event_qr") / report["total_checkins"] * 100)
    assert share == AUTO_SHARE_PCT
    assert share > 50, "the scenario's 'most' — the share reads as automatic"
