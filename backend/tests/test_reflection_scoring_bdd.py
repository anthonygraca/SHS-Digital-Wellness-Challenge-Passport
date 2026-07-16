"""Executable Gherkin for FR-E5 — reflection scoring + human override (US-19).

Binds tests/features/reflection_scoring.feature, a verbatim copy of the scenarios in
docs/features.md. The plain-pytest edge cases live in test_reflection_scoring.py (the
student surface) and test_reflection_override.py (the admin one); the scorer's own
behaviour is unit-tested in test_reflection_scorer.py.

Four notes on binding these scenarios:

"Then it is scored against the rubric with short feedback" is the load-bearing one, and
the fixture text is chosen to score strictly *between* 0.0 and 1.0. Asserting a bare
0.0 or 1.0 would be indistinguishable from a coin-flip or a constant — an interior score
is what makes "scored against the rubric" observable rather than merely claimed. The
step does not assert an exact number: that would pin the stub's arithmetic, and this file
is the contract, not the stub's unit test.

The feature title says "AI-scored" and the tag is @ai, but nothing on this branch is
AI — the scorer is a deterministic stub behind the ReflectionScorer seam. The Gherkin
is copied verbatim because the doc is the contract; the assertions test what the code
does, which is score, store, and return feedback. When a model lands behind the seam,
these scenarios pass unchanged. That is the point of the seam, and it is why the stored
``scored_by`` is "auto" and never "ai".

Scenario 2's Given "an AI-scored reflection" is the whole of scenario 1 — so the
``scored_reflection`` fixture performs the submit and captures the ids while still on the
student session. It must capture them there: the admin route is addressed by
challenge/task/item, and the student surface never speaks those, so the ids are
unreachable once the session flips.

"Then the stored score updates" is proved by re-reading, not by trusting the PATCH echo —
a response body proves the server can compose JSON, not that a row changed. Same reasoning
as FR-E4's storage step.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/reflection_scoring.feature")

ADMIN = "admin@csub.edu"
STUDENT = "s1@csub.edu"

PROMPT = "What is one number from today's labs you want to change, and how?"
OUTCOME_TAG = "know-your-numbers"
RUBRIC = (
    "Names a specific number; names a specific doable action; "
    "connects the action to the number."
)

# Scores strictly between 0.0 and 1.0: it engages with the rubric without parroting it,
# and it is shorter than the stub's length target. See the module docstring.
REFLECTION = (
    "My blood pressure was higher than I expected. I am going to walk for twenty "
    "minutes after dinner and recheck the number at the pharmacy next month."
)

OVERRIDE_SCORE = 0.25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _fetch_items(client, week_no: int) -> list[dict]:
    resp = client.get(f"/api/assessments/weeks/{week_no}/items")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _responses_url(ctx: dict) -> str:
    return (
        f"/api/challenges/{ctx['challenge_id']}/tasks/{ctx['task_id']}"
        f"/items/{ctx['item_id']}/responses"
    )


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


@pytest.fixture
def reflection(client) -> dict:
    """A published challenge whose week 1 carries one rubric-tagged reflection.

    Ends on a *student* session — the state scenario 1 submits from. Enrolling mints the
    Student row the stored response is foreign-keyed to. The challenge and task ids come
    back with it because scenario 2's admin steps need them.
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
        json={"title": "Know your numbers", "required": True},
    ).json()
    item = client.post(
        f"/api/challenges/{challenge['id']}/tasks/{task['id']}/items",
        json={
            "item_type": "reflection",
            "prompt": PROMPT,
            "outcome_tag": OUTCOME_TAG,
            "rubric": RUBRIC,
        },
    ).json()
    assert client.post(f"/api/challenges/{challenge['id']}/publish").status_code == 200

    _sign_in_as(client, "student", STUDENT)
    assert client.post("/enrollment").status_code == 200

    return {
        "challenge_id": challenge["id"],
        "task_id": task["id"],
        "item_id": item["id"],
        "rubric": item["rubric"],
        "outcome_tag": item["outcome_tag"],
        "week_no": task["position"],
    }


@pytest.fixture
def scored_reflection(client, reflection) -> dict:
    """Scenario 2's Given: a reflection that has been submitted and scored.

    This is scenario 1's flow. The response id is captured here, on the student session,
    because the admin route is reached by challenge/task/item and the student surface
    never speaks those ids.
    """
    resp = client.post(
        f"/api/assessments/items/{reflection['item_id']}/reflections",
        json={"text": REFLECTION},
    )
    assert resp.status_code == 201, resp.text
    return {**reflection, "result": resp.json()}


# ---------------------------------------------------------------------------
# Scenario: Reflection is AI-scored against a rubric
# ---------------------------------------------------------------------------


@given("a reflection item with a rubric and a learning-outcome tag")
def a_reflection_item_with_a_rubric_and_a_tag(reflection, context):
    assert reflection["rubric"] == RUBRIC
    assert reflection["outcome_tag"] == OUTCOME_TAG
    context.update(reflection)


@when("I submit a free-text reflection")
def i_submit_a_free_text_reflection(client, context):
    resp = client.post(
        f"/api/assessments/items/{context['item_id']}/reflections",
        json={"text": REFLECTION},
    )
    assert resp.status_code == 201, resp.text
    context["result"] = resp.json()


@then("it is scored against the rubric with short feedback")
def it_is_scored_against_the_rubric_with_short_feedback(context):
    result = context["result"]

    # Strictly interior: a 0.0 or a 1.0 here would be satisfied by a scorer that ignored
    # the rubric entirely. See the module docstring.
    assert 0.0 < result["score"] < 1.0, result

    assert result["feedback"].strip(), "scored, but said nothing"
    assert len(result["feedback"]) <= 200, "short feedback, not an essay"

    # The tag travels as its own field so the UI can render it as an element rather than
    # parse it back out of the prose.
    assert result["outcomeTag"] == OUTCOME_TAG


@then('the response is stored with scored_by "auto"')
def the_response_is_stored_with_scored_by_auto(client, context):
    items = _fetch_items(client, context["week_no"])
    item = next(i for i in items if i["id"] == context["item_id"])

    stored = item["yourResponse"]
    assert stored is not None, "the POST echoed a score but persisted nothing"
    assert stored["score"] == context["result"]["score"]
    assert stored["response"] == REFLECTION
    assert stored["feedback"] == context["result"]["feedback"]
    assert stored["scoredBy"] == "auto"


# ---------------------------------------------------------------------------
# Scenario: Admin overrides an AI score
# ---------------------------------------------------------------------------


@given("an AI-scored reflection")
def an_ai_scored_reflection(scored_reflection, context):
    context.update(scored_reflection)
    assert context["result"]["scoredBy"] == "auto"


@when("an admin adjusts the score")
def an_admin_adjusts_the_score(client, context):
    # The scenario changes actor mid-flow: the student submitted, an admin corrects.
    _sign_in_as(client, "staff", ADMIN)

    listed = client.get(_responses_url(context))
    assert listed.status_code == 200, listed.text
    response_id = listed.json()[0]["id"]

    resp = client.patch(
        f"{_responses_url(context)}/{response_id}", json={"score": OVERRIDE_SCORE}
    )
    assert resp.status_code == 200, resp.text
    context["response_id"] = response_id
    context["override"] = resp.json()


@then("the stored score updates")
def the_stored_score_updates(client, context):
    assert context["override"]["score"] != context["result"]["score"], (
        "the test would pass even if nothing changed"
    )

    # Re-read rather than trust the PATCH echo — see the module docstring.
    row = next(
        r
        for r in client.get(_responses_url(context)).json()
        if r["id"] == context["response_id"]
    )
    assert row["score"] == OVERRIDE_SCORE


@then('scored_by is set to "human"')
def scored_by_is_set_to_human(client, context):
    row = next(
        r
        for r in client.get(_responses_url(context)).json()
        if r["id"] == context["response_id"]
    )
    assert row["scored_by"] == "human"

    # The override corrects the score, not the record of what was overridden.
    assert row["ai_feedback"] == context["result"]["feedback"]
