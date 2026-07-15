"""Executable Gherkin for FR-F3 — Engagement report (US-23).

Binds tests/features/engagement_report.feature, a verbatim copy of the scenario in
docs/features.md. The plain-pytest edge cases — RBAC, no-active-challenge, campus
isolation, empty shapes, the reconciliation gap — live in test_engagement_report.py.

Three notes on binding this scenario:

Like US-22's feature file and unlike US-21's, this one has no Background — it opens
on a `When`. The two challenges, the cohort and the views are built by an autouse
fixture instead of a @given. The doc is the contract, so a Background cannot simply
be added to make the seam prettier.

The content views are seeded by *really* posting them: a student signs in and opens
week details, or scans and is handed a tip. Writing ContentView rows directly would
prove the query and nothing else — the point of instrumenting the passport (US-23)
is that opening a week reaches the table, and only driving the real routes shows it.

The guide sessions are the exception, and are direct-inserted. Nothing mints one
until the conversational guide lands (US-16), so there is no route to drive. This is
the same move test_attendance_report.py makes for its `staff` bucket and for the same
reason: without a row the scenario would pass against a hard-coded zero, and "I see
counts of guide chat sessions" would be satisfied by a report that cannot count them.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then, when

from app.models.engagement import GuideSession
from app.models.student import Student
from app.services.qr import mint_event_token

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/engagement_report.feature")

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu"]

# Two published challenges, deliberately given different engagement so that
# "viewed per challenge" has something to distinguish. ACTIVE starts later, so it
# is the one an unparameterised report answers for.
ACTIVE_WEEK_DETAIL = 4
ACTIVE_TIP = 2
ACTIVE_TOTAL = ACTIVE_WEEK_DETAIL + ACTIVE_TIP  # 6
ACTIVE_GUIDE = 3

PRIOR_WEEK_DETAIL = 2
PRIOR_TIP = 1
PRIOR_TOTAL = PRIOR_WEEK_DETAIL + PRIOR_TIP  # 3
PRIOR_GUIDE = 1


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _publish_challenge(client, name: str, semester: str, start: str, weeks: int):
    """A published challenge with N weeks. Assumes (and leaves) an admin session."""
    challenge = client.post(
        "/api/challenges",
        json={
            "name": name,
            "semester": semester,
            "start_date": start,
            "end_date": "2025-12-15",
            "theme_id": "stranger-things",
        },
    ).json()
    task_ids = {
        week_no: client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": f"Week {week_no}", "required": True},
        ).json()["id"]
        for week_no in range(1, weeks + 1)
    }
    client.post(f"/api/challenges/{challenge['id']}/publish")
    return challenge["id"], task_ids


def _open_week(client, week_no: int, subject: str) -> None:
    """Open a week's detail sheet, the way the passport does (US-23 instrumentation).

    Signing in as the student and posting the week number, rather than writing the
    row directly, is what makes this a content view the report counts and not just
    a fixture that happens to say "week_detail".
    """
    _sign_in_as(client, "student", subject)
    resp = client.post(
        "/api/content-views", json={"weekNo": week_no, "contentRef": "week_detail"}
    )
    assert resp.status_code == 204, resp.text


def _scan(client, task_id: int, subject: str) -> None:
    """Scan an event QR — which hands the student a tip, and so records a `tip` view.

    Nothing here mentions content: the tip view is written by the scan route itself,
    because that route is what delivers the tip. Driving the real scan is the only
    way to show that.
    """
    _sign_in_as(client, "student", subject)
    resp = client.post("/api/checkins/scan", json={"token": mint_event_token(task_id)})
    assert resp.status_code == 200, resp.text


def _seed_guide_sessions(db_sessionmaker, challenge_id: int, count: int) -> None:
    """Direct-insert the rows US-16 will one day write. See the module docstring."""
    with db_sessionmaker() as db:
        student = db.query(Student).filter_by(sso_subject=STUDENTS[0]).one()
        for _ in range(count):
            db.add(GuideSession(student_id=student.id, challenge_id=challenge_id))
        db.commit()


def _fetch_report(client, challenge_id: int | None = None) -> dict:
    params = {} if challenge_id is None else {"challenge_id": challenge_id}
    resp = client.get("/api/reports/engagement", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _counts(report: dict) -> dict[str, int]:
    return {v["content_ref"]: v["count"] for v in report["content_views"]}


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


@pytest.fixture(autouse=True)
def seeded(client, db_sessionmaker, context):
    """Two published challenges, each with its own engagement.

    An autouse fixture rather than a @given because this feature file has no
    Background — see the module docstring. Ends on an admin session, which is the
    state the scenario opens in.

    The prior challenge is seeded *first*, while it is still the active one: the
    content-view write path only ever resolves the campus's active challenge, so
    seeding in start-date order is what lets both challenges' views go through the
    real routes rather than one of them being hand-written into the table.
    """
    _sign_in_as(client, "staff", ADMIN)

    prior_id, prior_tasks = _publish_challenge(
        client, "Spring 2025 - Portal Guide", "Spring 2025", "2025-01-15", weeks=2
    )
    context["prior_id"] = prior_id

    # 2 week_detail + 1 tip, while this challenge is the active one.
    _open_week(client, 1, STUDENTS[0])
    _open_week(client, 2, STUDENTS[0])
    _scan(client, prior_tasks[1], STUDENTS[0])

    _sign_in_as(client, "staff", ADMIN)
    active_id, active_tasks = _publish_challenge(
        client, "Fall 2025 - Stranger Things", "Fall 2025", "2025-09-01", weeks=4
    )
    context["active_id"] = active_id

    # 4 week_detail — including the same student opening week 1 twice, which is two
    # views of one week, not a duplicate to collapse.
    _open_week(client, 1, STUDENTS[0])
    _open_week(client, 1, STUDENTS[0])
    _open_week(client, 2, STUDENTS[0])
    _open_week(client, 1, STUDENTS[1])
    # 2 tips. Disjoint by (student, week) — uq_checkin_student_task would reject an
    # overlap, and a rejected scan hands out no tip.
    _scan(client, active_tasks[1], STUDENTS[0])
    _scan(client, active_tasks[2], STUDENTS[1])

    _seed_guide_sessions(db_sessionmaker, active_id, ACTIVE_GUIDE)
    _seed_guide_sessions(db_sessionmaker, prior_id, PRIOR_GUIDE)

    _sign_in_as(client, "staff", ADMIN)


@when("I open the engagement report")
def i_open_the_engagement_report(client, context):
    context["report"] = _fetch_report(client)


@then("I see counts of content views")
def i_see_counts_of_content_views(context):
    report = context["report"]
    # Both refs, always — a bucket that vanished when nobody had triggered it would
    # make "tip: 0" indistinguishable from "tips: not reported".
    assert _counts(report) == {"week_detail": ACTIVE_WEEK_DETAIL, "tip": ACTIVE_TIP}
    # The total is the number of views that actually exist, and the buckets
    # reconcile against it. Internal consistency alone would be vacuous — 0 == 0
    # satisfies a sum check.
    assert report["total_content_views"] == ACTIVE_TOTAL
    assert sum(_counts(report).values()) == report["total_content_views"]


@then("I see counts of guide chat sessions")
def i_see_counts_of_guide_chat_sessions(context):
    # A real count of real rows, not the structural zero the report shows in
    # production until US-16 ships. That zero is asserted separately, in
    # test_engagement_report.py — here the point is that the number can move.
    assert context["report"]["guide_sessions"] == ACTIVE_GUIDE


@then("both can be viewed per challenge")
def both_can_be_viewed_per_challenge(client, context):
    """ "Both" is the load-bearing word: views *and* guide sessions must re-scope.

    The prior challenge is only reachable by asking for it — it is published but
    not active, so without the challenge_id parameter its semester would be
    unreportable. Every count differs from the active challenge's, so a report that
    ignored the parameter could not pass this by coincidence.
    """
    prior = _fetch_report(client, context["prior_id"])

    assert prior["challenge"]["id"] == context["prior_id"]
    assert _counts(prior) == {"week_detail": PRIOR_WEEK_DETAIL, "tip": PRIOR_TIP}
    assert prior["total_content_views"] == PRIOR_TOTAL
    assert prior["guide_sessions"] == PRIOR_GUIDE

    # And asking for the active one by id agrees with asking for it by default, so
    # the parameter selects a challenge rather than changing what is counted.
    active = _fetch_report(client, context["active_id"])
    assert active == context["report"]
