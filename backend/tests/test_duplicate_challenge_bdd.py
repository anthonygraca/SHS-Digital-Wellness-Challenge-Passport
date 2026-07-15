"""Executable Gherkin for FR-B6 — Duplicate prior challenge (US-14).

Binds tests/features/duplicate_challenge.feature, which is a verbatim copy of the
scenarios in docs/features.md. The plain-pytest edge cases — naming/suffix rules,
409s, RBAC, enrollments not copied — live in test_challenges.py alongside the rest
of the challenge API.

Two honest notes on binding these scenarios:

"When I duplicate it" takes no arguments, so it posts no body. That is the same
path the bare API offers, and it is deliberately *not* the path the admin UI takes
(the UI sends a semester). The UI's own behaviour is covered by
ChallengeBuilder.test.tsx.

"And the copy is independent of the original" is a claim about identity, not about
a later edit — the edit is scenario 2's job. It is bound here as: every row the
copy owns is a new row, so the two graphs share nothing to begin with.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

# Binds every scenario in the file to this module. Without this call pytest-bdd
# collects nothing — .feature files are not auto-discovered.
scenarios("features/duplicate_challenge.feature")

ADMIN = "admin@csub.edu"
THEME = "stranger-things"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _build_prior_challenge(client, context: dict, name: str) -> None:
    """A published challenge with two tasks, a quiz item, and a theme."""
    _sign_in_as(client, "staff", ADMIN)
    challenge = client.post(
        "/api/challenges",
        json={
            "name": name,
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
            "theme_id": THEME,
        },
    ).json()
    context["original_id"] = challenge["id"]

    for title in ("Week 1 - Vision Check", "Week 2 - Flu Shot"):
        task = client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": title, "caption": f"Caption for {title}", "required": True},
        ).json()
        context.setdefault("task_ids", []).append(task["id"])

    client.post(
        f"/api/challenges/{challenge['id']}/tasks/{context['task_ids'][0]}/items",
        json={
            "item_type": "mcq",
            "prompt": "How many hours of sleep are recommended?",
            "outcome_tag": "sleep_hygiene",
            "options": ["6", "7", "8", "9"],
            "answer_key": "8",
        },
    )
    client.post(f"/api/challenges/{challenge['id']}/publish")
    context["original"] = client.get(f"/api/challenges/{challenge['id']}").json()


def _duplicate(client, context: dict) -> None:
    resp = client.post(f"/api/challenges/{context['original_id']}/duplicate")
    assert resp.status_code == 201, resp.text
    context["copy"] = resp.json()


def _strip_identity(challenge: dict) -> list[dict]:
    """The authored content of a challenge's tasks, minus anything row-specific.

    ids, timestamps, the parent challenge_id, and qr_token (derived from the task
    id) all *must* differ between the original and the copy, so comparing them
    verbatim would fail for the right reason and hide the wrong one.
    """
    drop = {"id", "challenge_id", "task_id", "created_at", "updated_at", "qr_token"}

    def authored(row: dict) -> dict:
        return {k: v for k, v in row.items() if k not in drop and k != "assessment_items"}

    return [
        {
            **authored(task),
            "assessment_items": [authored(i) for i in task["assessment_items"]],
        }
        for task in challenge["tasks"]
    ]


@pytest.fixture
def context() -> dict:
    """Per-scenario scratch space (ids, responses) shared across steps."""
    return {}


# ---------------------------------------------------------------------------
# Scenario: Duplicate creates an editable draft
# ---------------------------------------------------------------------------


@given(parsers.parse('a prior challenge "{name}"'))
def a_prior_challenge(client, context, name):
    _build_prior_challenge(client, context, name)


@when("I duplicate it")
def i_duplicate_it(client, context):
    _duplicate(client, context)


@then("a new draft challenge is created with the same tasks, quiz items, and theme")
def copy_is_a_draft_with_the_same_content(client, context):
    copy, original = context["copy"], context["original"]

    assert copy["id"] != original["id"]
    assert copy["status"] == "draft"
    assert original["status"] == "published"  # the copy did not inherit it
    assert copy["theme_id"] == THEME
    # Tasks in order, their quiz items, and every authored attribute.
    assert _strip_identity(copy) == _strip_identity(original)
    assert [t["title"] for t in copy["tasks"]] == [
        "Week 1 - Vision Check",
        "Week 2 - Flu Shot",
    ]
    assert copy["tasks"][0]["assessment_items"][0]["options"] == ["6", "7", "8", "9"]


@then("the copy is independent of the original")
def copy_shares_no_rows_with_the_original(client, context):
    copy, original = context["copy"], context["original"]

    copy_task_ids = {t["id"] for t in copy["tasks"]}
    original_task_ids = {t["id"] for t in original["tasks"]}
    assert copy_task_ids.isdisjoint(original_task_ids)

    def item_ids(challenge: dict) -> set[int]:
        return {i["id"] for t in challenge["tasks"] for i in t["assessment_items"]}

    assert item_ids(copy).isdisjoint(item_ids(original))
    assert item_ids(copy)  # the copy really has items to be disjoint about


# ---------------------------------------------------------------------------
# Scenario: Editing the copy does not affect the original
# ---------------------------------------------------------------------------


@given("a duplicated draft challenge")
def a_duplicated_draft_challenge(client, context):
    _build_prior_challenge(client, context, "Fall 2025 - Stranger Things")
    _duplicate(client, context)


@when("I change a task in the copy")
def i_change_a_task_in_the_copy(client, context):
    copy = context["copy"]
    resp = client.patch(
        f"/api/challenges/{copy['id']}/tasks/{copy['tasks'][0]['id']}",
        json={"title": "Week 1 - Rewritten", "caption": "Rewritten caption"},
    )
    assert resp.status_code == 200, resp.text


@then("the original challenge is unchanged")
def the_original_is_unchanged(client, context):
    refetched = client.get(f"/api/challenges/{context['original_id']}").json()
    assert _strip_identity(refetched) == _strip_identity(context["original"])
    assert refetched["tasks"][0]["title"] == "Week 1 - Vision Check"
