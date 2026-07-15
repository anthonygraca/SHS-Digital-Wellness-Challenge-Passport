"""Executable Gherkin for FR-E4 — MCQ auto-scoring (US-18).

Binds tests/features/mcq_scoring.feature, a verbatim copy of the scenarios in
docs/features.md. The plain-pytest edge cases — RBAC, campus isolation, the
answer-key leak, unknown options, re-submission — live in test_mcq_scoring.py.

Three notes on binding these scenarios:

Scenario 2 has no Given. That is how the doc reads, so that is how this file reads:
manual_override.feature carries a Background only because features.md carries one,
and duplicate_challenge.feature repeats its Given per scenario for the same reason —
neither licenses inventing one here. Instead the setup lives in the ``mcq`` fixture,
which the Given step and scenario 2's When step both request, so scenario 2 gets an
identical MCQ without a line of Gherkin the contract does not have.

"Then I see an instant correct result" is a claim about the *submit response*.
"Instantly" means the score comes back from the POST itself rather than from a job
the client waits on, so the assertion is on the POST body — the second round-trip
that does not exist is the point.

"And the score is stored against the learning-outcome tag" needs a read to prove
storage: the POST echoing a score proves only that the server can do arithmetic. So
that step re-fetches the week's items and asserts the persisted response sits on an
item carrying the expected tag.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/mcq_scoring.feature")

ADMIN = "admin@csub.edu"
STUDENT = "s1@csub.edu"

WEEK_NO = 1
PROMPT = "How often should a healthy adult have a comprehensive eye exam?"
OUTCOME_TAG = "vision-care"
OPTIONS = [
    "Only when my vision seems blurry",
    "Every 1-2 years",
    "Once, when I turn 18",
    "Every 5 years",
]
CORRECT = "Every 1-2 years"
INCORRECT = "Once, when I turn 18"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _submit(client, item_id: int, answer: str) -> dict:
    resp = client.post(
        f"/api/assessments/items/{item_id}/responses", json={"answer": answer}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _fetch_items(client, week_no: int) -> list[dict]:
    resp = client.get(f"/api/assessments/weeks/{week_no}/items")
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


@pytest.fixture
def mcq(client) -> dict:
    """A published challenge whose week 1 carries one tagged MCQ, student signed in.

    Ends on a *student* session, which is the state both scenarios submit from.
    Enrolling mints the Student row the stored response is foreign-keyed to.

    This is the Given of scenario 1 and the unwritten Given of scenario 2 — see the
    module docstring.
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
    task = client.post(
        f"/api/challenges/{challenge['id']}/tasks",
        json={"title": "Vision screening", "required": True},
    ).json()
    item = client.post(
        f"/api/challenges/{challenge['id']}/tasks/{task['id']}/items",
        json={
            "item_type": "mcq",
            "prompt": PROMPT,
            "outcome_tag": OUTCOME_TAG,
            "options": OPTIONS,
            "answer_key": CORRECT,
        },
    ).json()
    assert client.post(f"/api/challenges/{challenge['id']}/publish").status_code == 200

    _sign_in_as(client, "student", STUDENT)
    assert client.post("/enrollment").status_code == 200

    return {
        "item_id": item["id"],
        "answer_key": item["answer_key"],
        "outcome_tag": item["outcome_tag"],
        "week_no": task["position"],
    }


# ---------------------------------------------------------------------------
# Scenario: Correct answer is scored instantly
# ---------------------------------------------------------------------------


@given("an MCQ with a defined answer key")
def an_mcq_with_a_defined_answer_key(mcq):
    assert mcq["answer_key"] == CORRECT
    assert mcq["outcome_tag"] == OUTCOME_TAG


@when("I submit the correct option")
def i_submit_the_correct_option(client, context, mcq):
    context["result"] = _submit(client, mcq["item_id"], CORRECT)


@then("I see an instant correct result")
def i_see_an_instant_correct_result(context):
    result = context["result"]
    assert result["correct"] is True
    assert result["score"] == 1.0
    assert result["scoredBy"] == "auto"


# ---------------------------------------------------------------------------
# Scenario: Incorrect answer is scored instantly with feedback
# ---------------------------------------------------------------------------


@when("I submit an incorrect option")
def i_submit_an_incorrect_option(client, context, mcq):
    # `mcq` is the scenario's unwritten Given — see the module docstring.
    context["result"] = _submit(client, mcq["item_id"], INCORRECT)


@then("I see an instant incorrect result")
def i_see_an_instant_incorrect_result(context):
    result = context["result"]
    assert result["correct"] is False
    assert result["score"] == 0.0
    assert result["scoredBy"] == "auto"

    # The scenario is titled "...with feedback", so an incorrect result owes more
    # than a verdict: it names the option the student should have picked.
    assert result["correctOption"] == CORRECT
    assert CORRECT in result["feedback"]


# ---------------------------------------------------------------------------
# Shared: the storage assertion (both scenarios)
# ---------------------------------------------------------------------------


@then("the score is stored against the learning-outcome tag")
def the_score_is_stored_against_the_learning_outcome_tag(client, context, mcq):
    items = _fetch_items(client, mcq["week_no"])
    item = next(i for i in items if i["id"] == mcq["item_id"])

    assert item["outcomeTag"] == OUTCOME_TAG

    stored = item["yourResponse"]
    assert stored is not None, "the POST echoed a score but persisted nothing"
    assert stored["score"] == context["result"]["score"]
    assert stored["correct"] == context["result"]["correct"]
    assert stored["scoredBy"] == "auto"
