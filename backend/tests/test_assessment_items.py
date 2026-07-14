from __future__ import annotations

"""Tests for FR-B3 — Attach assessment items with outcome tags (US-12).

Gherkin scenarios covered
--------------------------
Scenario: Attach an MCQ with an answer key and outcome tag
  When I add an MCQ with a prompt, options, an answer key, and a learning-outcome tag
  Then the MCQ is saved against the task
  And it is linked to that learning-outcome tag

Scenario: Attach a reflection with a rubric and outcome tag
  When I add a reflection item with a prompt, a rubric, and a learning-outcome tag
  Then the reflection is saved against the task
  And it is linked to that learning-outcome tag
"""

# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_challenges.py)
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = "user@csub.edu") -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _create_challenge(client, **overrides):
    payload = {
        "name": "Fall 2025 Wellness",
        "semester": "Fall 2025",
        "start_date": "2025-09-01",
        "end_date": "2025-12-15",
        **overrides,
    }
    return client.post("/api/challenges", json=payload)


def _add_task(client, challenge_id: int, **overrides):
    payload = {
        "title": "Week 1 – Vision Check",
        "caption": "Get your eyes examined.",
        "activity_type": "health_screening",
        "location": "SHS Lobby",
        "date_window_start": "2025-09-01",
        "date_window_end": "2025-09-07",
        "prize": "Raffle entry",
        "required": True,
        **overrides,
    }
    return client.post(f"/api/challenges/{challenge_id}/tasks", json=payload)


def _add_mcq(client, challenge_id: int, task_id: int, **overrides):
    payload = {
        "item_type": "mcq",
        "prompt": "How many hours of sleep are recommended for adults?",
        "outcome_tag": "sleep-hygiene",
        "options": ["6", "7-9", "10", "12"],
        "answer_key": "7-9",
        **overrides,
    }
    return client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items", json=payload
    )


def _add_reflection(client, challenge_id: int, task_id: int, **overrides):
    payload = {
        "item_type": "reflection",
        "prompt": "Describe one change you made to improve your sleep this week.",
        "outcome_tag": "sleep-hygiene",
        "rubric": "1 – no change described; 2 – vague; 3 – specific actionable change",
        **overrides,
    }
    return client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items", json=payload
    )


# ---------------------------------------------------------------------------
# Background fixture helper
# ---------------------------------------------------------------------------


def _setup(client):
    """Sign in as admin, create a draft challenge, add one task; return ids."""
    _sign_in_as(client, "staff")
    challenge_id = _create_challenge(client).json()["id"]
    task_id = _add_task(client, challenge_id).json()["id"]
    return challenge_id, task_id


# ---------------------------------------------------------------------------
# Scenario: Attach an MCQ with an answer key and outcome tag
# ---------------------------------------------------------------------------


class TestAttachMCQ:
    def test_mcq_is_saved_against_task(self, client):
        """MCQ saved; response includes all submitted fields."""
        challenge_id, task_id = _setup(client)
        resp = _add_mcq(client, challenge_id, task_id)

        assert resp.status_code == 201
        body = resp.json()
        assert body["item_type"] == "mcq"
        assert body["task_id"] == task_id
        assert body["prompt"] == "How many hours of sleep are recommended for adults?"
        assert body["options"] == ["6", "7-9", "10", "12"]
        assert body["answer_key"] == "7-9"

    def test_mcq_is_linked_to_outcome_tag(self, client):
        """outcome_tag is persisted and returned on the item."""
        challenge_id, task_id = _setup(client)
        resp = _add_mcq(client, challenge_id, task_id)

        assert resp.json()["outcome_tag"] == "sleep-hygiene"

    def test_mcq_appears_in_task_item_list(self, client):
        """GET items returns the newly created MCQ."""
        challenge_id, task_id = _setup(client)
        item_id = _add_mcq(client, challenge_id, task_id).json()["id"]

        resp = client.get(f"/api/challenges/{challenge_id}/tasks/{task_id}/items")
        assert resp.status_code == 200
        ids = [i["id"] for i in resp.json()]
        assert item_id in ids

    def test_mcq_answer_key_not_in_options_rejected(self, client):
        """answer_key must be one of the provided options."""
        challenge_id, task_id = _setup(client)
        resp = _add_mcq(client, challenge_id, task_id, answer_key="not-an-option")

        assert resp.status_code == 422

    def test_mcq_requires_at_least_two_options(self, client):
        """options list must have at least 2 entries."""
        challenge_id, task_id = _setup(client)
        resp = _add_mcq(
            client, challenge_id, task_id, options=["only-one"], answer_key="only-one"
        )

        assert resp.status_code == 422

    def test_mcq_reflection_fields_are_null(self, client):
        """rubric is null on an MCQ item."""
        challenge_id, task_id = _setup(client)
        body = _add_mcq(client, challenge_id, task_id).json()

        assert body["rubric"] is None


# ---------------------------------------------------------------------------
# Scenario: Attach a reflection with a rubric and outcome tag
# ---------------------------------------------------------------------------


class TestAttachReflection:
    def test_reflection_is_saved_against_task(self, client):
        """Reflection saved; response includes all submitted fields."""
        challenge_id, task_id = _setup(client)
        resp = _add_reflection(client, challenge_id, task_id)

        assert resp.status_code == 201
        body = resp.json()
        assert body["item_type"] == "reflection"
        assert body["task_id"] == task_id
        assert (
            body["prompt"]
            == "Describe one change you made to improve your sleep this week."
        )
        assert (
            body["rubric"]
            == "1 – no change described; 2 – vague; 3 – specific actionable change"
        )

    def test_reflection_is_linked_to_outcome_tag(self, client):
        """outcome_tag is persisted and returned on the item."""
        challenge_id, task_id = _setup(client)
        resp = _add_reflection(client, challenge_id, task_id)

        assert resp.json()["outcome_tag"] == "sleep-hygiene"

    def test_reflection_appears_in_task_item_list(self, client):
        """GET items returns the newly created reflection."""
        challenge_id, task_id = _setup(client)
        item_id = _add_reflection(client, challenge_id, task_id).json()["id"]

        resp = client.get(f"/api/challenges/{challenge_id}/tasks/{task_id}/items")
        assert resp.status_code == 200
        ids = [i["id"] for i in resp.json()]
        assert item_id in ids

    def test_reflection_mcq_fields_are_null(self, client):
        """options and answer_key are null on a reflection item."""
        challenge_id, task_id = _setup(client)
        body = _add_reflection(client, challenge_id, task_id).json()

        assert body["options"] is None
        assert body["answer_key"] is None


# ---------------------------------------------------------------------------
# Mixed items on the same task
# ---------------------------------------------------------------------------


class TestMixedItems:
    def test_task_can_hold_both_mcq_and_reflection(self, client):
        """A task may have multiple items of different types."""
        challenge_id, task_id = _setup(client)
        mcq_id = _add_mcq(client, challenge_id, task_id).json()["id"]
        ref_id = _add_reflection(client, challenge_id, task_id).json()["id"]

        items = client.get(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items"
        ).json()
        ids = {i["id"] for i in items}
        assert {mcq_id, ref_id} == ids

    def test_items_carried_on_task_out(self, client):
        """assessment_items appear inline when the challenge is fetched."""
        challenge_id, task_id = _setup(client)
        _add_mcq(client, challenge_id, task_id)
        _add_reflection(client, challenge_id, task_id)

        challenge = client.get(f"/api/challenges/{challenge_id}").json()
        task = next(t for t in challenge["tasks"] if t["id"] == task_id)
        assert len(task["assessment_items"]) == 2
        types = {i["item_type"] for i in task["assessment_items"]}
        assert types == {"mcq", "reflection"}

    def test_different_outcome_tags_preserved(self, client):
        """Each item's outcome_tag is stored independently."""
        challenge_id, task_id = _setup(client)
        _add_mcq(client, challenge_id, task_id, outcome_tag="nutrition")
        _add_reflection(client, challenge_id, task_id, outcome_tag="mental-health")

        items = client.get(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items"
        ).json()
        tags = {i["outcome_tag"] for i in items}
        assert tags == {"nutrition", "mental-health"}


# ---------------------------------------------------------------------------
# CRUD: update and delete
# ---------------------------------------------------------------------------


class TestItemCRUD:
    def test_update_mcq_prompt(self, client):
        challenge_id, task_id = _setup(client)
        item_id = _add_mcq(client, challenge_id, task_id).json()["id"]

        resp = client.patch(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items/{item_id}",
            json={"prompt": "Updated question text"},
        )
        assert resp.status_code == 200
        assert resp.json()["prompt"] == "Updated question text"

    def test_update_outcome_tag(self, client):
        challenge_id, task_id = _setup(client)
        item_id = _add_reflection(client, challenge_id, task_id).json()["id"]

        resp = client.patch(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items/{item_id}",
            json={"outcome_tag": "exercise"},
        )
        assert resp.status_code == 200
        assert resp.json()["outcome_tag"] == "exercise"

    def test_delete_item_removes_it(self, client):
        challenge_id, task_id = _setup(client)
        item_id = _add_mcq(client, challenge_id, task_id).json()["id"]

        resp = client.delete(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items/{item_id}"
        )
        assert resp.status_code == 204

        items = client.get(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items"
        ).json()
        assert all(i["id"] != item_id for i in items)

    def test_get_nonexistent_item_returns_404(self, client):
        challenge_id, task_id = _setup(client)

        resp = client.patch(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items/99999",
            json={"prompt": "irrelevant"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_student_cannot_attach_item(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        task_id = _add_task(client, challenge_id).json()["id"]

        _sign_in_as(client, "student")
        resp = _add_mcq(client, challenge_id, task_id)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_attach_item(self, client):
        # Fresh client — never signed in.
        challenge_id = 1
        task_id = 1
        resp = client.post(
            f"/api/challenges/{challenge_id}/tasks/{task_id}/items",
            json={
                "item_type": "mcq",
                "prompt": "?",
                "outcome_tag": "x",
                "options": ["a", "b"],
                "answer_key": "a",
            },
        )
        assert resp.status_code == 401
