"""Executable Gherkin for FR-F4 — Learning-outcome aggregate report (US-24).

Binds tests/features/learning_outcome_report.feature, a verbatim copy of the two
scenarios in docs/features.md. The plain-pytest edge cases — RBAC,
no-active-challenge, campus isolation, the unanswered tag, the weighted mean, the
shapes an empty challenge takes — live in test_learning_outcome_report.py.

Three notes on binding these scenarios:

Unlike US-22's and US-23's feature files, this one opens on a `Given`, so the steps
are bound as @given rather than replaced by an autouse fixture. Neither Given
mentions the challenge or the items, though, and a report needs both to exist before
a response can be filed against one — so the autouse fixture builds *that* world and
the Givens put the scores in it. The split follows what the scenarios say: they are
about responses, not about authoring a challenge.

Every response here is seeded by *really* submitting it, through the same routes a
student's browser and an admin's dashboard post to — the MCQ answers through
POST /items/{id}/responses, the reflections through POST /items/{id}/reflections, and
the overrides through the admin PATCH US-19 added. Writing AssessmentResponse rows
directly would prove the query and nothing else; the claim behind FR-F4 is that the
scores students actually earn reach the report, and only driving the real routes
shows it.

That the overrides go through the real route is new. US-24 was written while US-19 was
still unmerged, when nothing could write scored_by="human" and the rows had to be
hand-inserted — the move test_engagement_report_bdd.py still makes for its guide
sessions, because a GuideSession genuinely has no writer. The exception ends the
moment a route exists, and one does. The scenario is stronger for it: the reflections
are AI-scored first and overridden second, so the aggregate has to reflect the human
value rather than the score the reflection originally earned, which no hand-written
row could have shown.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/learning_outcome_report.feature")

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu"]
REPORT = "/api/reports/outcomes"

CORRECT = "Every 1-2 years"
INCORRECT = "Once, when I turn 18"
OPTIONS = [CORRECT, INCORRECT, "Only when my vision seems blurry", "Every 5 years"]

# Three tags, deliberately not created in alphabetical order: "stress-management" is
# authored before "sleep-hygiene", so a report that simply echoed insertion order
# could not pass the ordering assertion by coincidence.
NUMBERS = "know-your-numbers"
STRESS = "stress-management"
SLEEP = "sleep-hygiene"

# know-your-numbers: two right, one wrong -> 2/3. stress-management: one each -> 1/2.
# The two means differ, and neither is 0 or 1, so a report that mixed the tags up or
# collapsed them into one number could not land on both.
NUMBERS_MEAN = 2 / 3
NUMBERS_N = 3
STRESS_MEAN = 0.5
STRESS_N = 2

AUTO_N = NUMBERS_N + STRESS_N  # 5
AUTO_SUM = 2.0 + 1.0  # 3.0
AUTO_MEAN = AUTO_SUM / AUTO_N  # 0.6

# What the admin overrides the AI's scores *to* (US-19 / FR-E5). Fractional on
# purpose: a rubric score is not a right/wrong 1.0-or-0.0, and a mean that only ever
# saw MCQ scores would never have to represent one. Neither value is one the stub
# scorer produces for these essays, so a report showing the AI's number instead of
# the human's could not land on the totals below.
HUMAN_SCORES = [0.5, 1.0]

REFLECTION_TEXT = (
    "I have been going to bed by eleven and keeping my phone across the room. "
    "I fall asleep faster and I am less irritable in my morning class."
)
SLEEP_MEAN = 0.75
SLEEP_N = 2

TOTAL_N = AUTO_N + SLEEP_N  # 7
TOTAL_SUM = AUTO_SUM + sum(HUMAN_SCORES)  # 4.5
TOTAL_MEAN = TOTAL_SUM / TOTAL_N  # ~0.642857 — and pointedly not AUTO_MEAN


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _add_mcq(client, challenge_id: int, task_id: int, outcome_tag: str) -> int:
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items",
        json={
            "item_type": "mcq",
            "prompt": f"An MCQ tagged {outcome_tag}?",
            "outcome_tag": outcome_tag,
            "options": OPTIONS,
            "answer_key": CORRECT,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_reflection(client, challenge_id: int, task_id: int, outcome_tag: str) -> int:
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items",
        json={
            "item_type": "reflection",
            "prompt": f"Reflect on {outcome_tag}.",
            "outcome_tag": outcome_tag,
            "rubric": "Mentions at least two habits and why they matter.",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _answer(client, item_id: int, subject: str, answer: str) -> None:
    """Submit an MCQ answer as the student, then restore the admin session.

    The real route, which is the point: it is what auto-scores the answer and writes
    the row the report later groups. Ends back on the admin session the scenario
    opens the report from.
    """
    _sign_in_as(client, "student", subject)
    resp = client.post(
        f"/api/assessments/items/{item_id}/responses", json={"answer": answer}
    )
    assert resp.status_code == 201, resp.text
    _sign_in_as(client, "staff", ADMIN)


def _submit_the_mcq_answers(client, context) -> None:
    """The quiz responses both scenarios stand on, through the real submit route."""
    _answer(client, context["numbers_item"], STUDENTS[0], CORRECT)
    _answer(client, context["numbers_item"], STUDENTS[1], CORRECT)
    _answer(client, context["numbers_item"], STUDENTS[2], INCORRECT)
    _answer(client, context["stress_item"], STUDENTS[0], CORRECT)
    _answer(client, context["stress_item"], STUDENTS[1], INCORRECT)


def _fetch_report(client, challenge_id: int | None = None) -> dict:
    params = {} if challenge_id is None else {"challenge_id": challenge_id}
    resp = client.get(REPORT, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_tag(report: dict) -> dict[str, dict]:
    return {o["outcome_tag"]: o for o in report["outcomes"]}


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


@pytest.fixture(autouse=True)
def seeded(client, context):
    """A published challenge with three tagged items and nobody's answers yet.

    The world the Givens put scores into — see the module docstring for why this is
    a fixture rather than a step. Ends on an admin session, which is the state both
    scenarios open their report from.
    """
    _sign_in_as(client, "staff", ADMIN)
    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 - Stranger Things",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
    ).json()
    context["challenge_id"] = challenge["id"]

    task_ids = [
        client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": f"Week {n}", "required": True},
        ).json()["id"]
        for n in range(1, 4)
    ]

    context["numbers_item"] = _add_mcq(client, challenge["id"], task_ids[0], NUMBERS)
    context["stress_item"] = _add_mcq(client, challenge["id"], task_ids[1], STRESS)
    context["sleep_item"] = _add_reflection(client, challenge["id"], task_ids[2], SLEEP)
    # The admin override route is nested under challenge/task/item, which is what
    # gives it campus isolation for free — so the scenario needs the task id too.
    context["sleep_task"] = task_ids[2]

    resp = client.post(f"/api/challenges/{challenge['id']}/publish")
    assert resp.status_code == 200, resp.text


@given("quiz responses scored against learning-outcome tags")
def quiz_responses_scored_against_tags(client, context):
    _submit_the_mcq_answers(client, context)


def _write_reflection(client, item_id: int, subject: str) -> None:
    """Submit a reflection as the student, then restore the admin session.

    Enrolling first because the reflection route requires a current student, exactly
    as US-19's own `scored` fixture does. Lands AI-scored (scored_by="auto") — the
    override below is what makes it human.
    """
    _sign_in_as(client, "student", subject)
    client.post("/enrollment")
    resp = client.post(
        f"/api/assessments/items/{item_id}/reflections", json={"text": REFLECTION_TEXT}
    )
    assert resp.status_code == 201, resp.text
    _sign_in_as(client, "staff", ADMIN)


def _override_scores(client, context, scores: list[float]) -> None:
    """Re-score the reflections by hand, as an admin on the dashboard would (US-19).

    Reads the responses back off the admin route rather than assuming ids: the
    override is addressed by response id, and that list is where an admin gets one.
    """
    responses_url = (
        f"/api/challenges/{context['challenge_id']}/tasks/{context['sleep_task']}"
        f"/items/{context['sleep_item']}/responses"
    )
    listed = client.get(responses_url)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == len(scores), f"expected {len(scores)} reflections, got {rows}"

    # Ordered by subject so a score belongs to a student rather than to whatever
    # order the route happened to return.
    for row, score in zip(sorted(rows, key=lambda r: r["student_subject"]), scores):
        # Auto until a human touches it — the precondition the override acts on.
        assert row["scored_by"] == "auto", row
        patched = client.patch(f"{responses_url}/{row['id']}", json={"score": score})
        assert patched.status_code == 200, patched.text
        assert patched.json()["scored_by"] == "human"


@given('some reflections were overridden with scored_by "human"')
def reflections_overridden_by_a_human(client, context):
    """AI-scored through the real route, then overridden through the real route.

    The MCQ answers go in too, and "some" is why: an aggregate made only of
    overridden scores could not show that they were *included* in anything — every
    number would be theirs by default. With auto-scored responses alongside, "the
    overridden scores are reflected in the totals" becomes a claim that can fail.
    """
    _submit_the_mcq_answers(client, context)
    for subject in STUDENTS[: len(HUMAN_SCORES)]:
        _write_reflection(client, context["sleep_item"], subject)
    _override_scores(client, context, HUMAN_SCORES)


@when("I open the learning-outcome report")
def i_open_the_learning_outcome_report(client, context):
    context["report"] = _fetch_report(client)


@when("I view the aggregate")
def i_view_the_aggregate(client, context):
    context["report"] = _fetch_report(client)


@then("I see aggregated scores grouped by outcome tag")
def i_see_aggregated_scores_grouped_by_outcome_tag(context):
    report = context["report"]
    outcomes = _by_tag(report)

    # Grouped by tag, not by item and not by student: each tag arrives once, carrying
    # the mean of every response filed against it and the count it was taken over.
    assert outcomes[NUMBERS]["mean_score"] == pytest.approx(NUMBERS_MEAN)
    assert outcomes[NUMBERS]["response_count"] == NUMBERS_N
    assert outcomes[STRESS]["mean_score"] == pytest.approx(STRESS_MEAN)
    assert outcomes[STRESS]["response_count"] == STRESS_N

    # The reflection tag nobody has answered is still a row. "Grouped by outcome tag"
    # means every tag the challenge has, not only the ones with scores — the argument
    # for that lives in test_learning_outcome_report.py, which owns the edge case.
    assert outcomes[SLEEP]["mean_score"] is None
    assert outcomes[SLEEP]["response_count"] == 0

    # Alphabetical, and stress-management was authored before sleep-hygiene, so
    # insertion order would have failed this.
    assert [o["outcome_tag"] for o in report["outcomes"]] == [NUMBERS, SLEEP, STRESS]

    # The totals the buckets reconcile against, counted over every response.
    assert report["total_responses"] == AUTO_N
    assert report["mean_score"] == pytest.approx(AUTO_MEAN)


@then("the overridden scores are reflected in the totals")
def the_overridden_scores_are_reflected_in_the_totals(context):
    """The load-bearing assertion is the last one: the mean *moved*.

    Everything above it would also pass against a report that counted the human rows
    in `total_responses` but quietly left their scores out of the mean. Pinning the
    total to a number that is only reachable with the overridden scores included is
    what makes "reflected in the totals" mean something.
    """
    report = context["report"]
    outcomes = _by_tag(report)

    # The overridden reflections land on their own tag, scores and all.
    assert outcomes[SLEEP]["mean_score"] == pytest.approx(SLEEP_MEAN)
    assert outcomes[SLEEP]["response_count"] == SLEEP_N
    assert outcomes[SLEEP]["human_scored_count"] == SLEEP_N

    # Counted as human without being filtered out for it: the auto-scored tags are
    # untouched and report no human scores of their own.
    assert report["total_human_scored"] == SLEEP_N
    assert outcomes[NUMBERS]["human_scored_count"] == 0
    assert outcomes[NUMBERS]["mean_score"] == pytest.approx(NUMBERS_MEAN)

    assert report["total_responses"] == TOTAL_N
    assert report["mean_score"] == pytest.approx(TOTAL_MEAN)
    assert report["mean_score"] != pytest.approx(AUTO_MEAN)
