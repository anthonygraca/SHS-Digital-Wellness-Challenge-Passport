from __future__ import annotations

"""Tests for FR-B1 (challenge creation) and FR-B2 (ordered weekly tasks).

Follows the same fixture/pattern as test_auth.py: in-memory SQLite, TestClient,
dependency_overrides[get_db].

Session cookie helpers
----------------------
_sign_in_as(client, affiliation) — POSTs an ACS assertion; the TestClient
    retains the HttpOnly session cookie for subsequent calls.
_admin_headers() is not needed — the cookie flow matches real usage.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = "user@csub.edu") -> None:
    """Authenticate via the mock IdP ACS and store the session cookie."""
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


# ---------------------------------------------------------------------------
# FR-B1 — Create challenge (Gherkin: "Create a challenge with core attributes")
# ---------------------------------------------------------------------------


class TestCreateChallenge:
    def test_admin_creates_draft_challenge(self, client):
        _sign_in_as(client, "staff")
        resp = _create_challenge(client)

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Fall 2025 Wellness"
        assert body["semester"] == "Fall 2025"
        assert body["status"] == "draft"
        assert body["campus_id"] == "csub"

    def test_challenge_saved_for_campus(self, client):
        _sign_in_as(client, "staff")
        _create_challenge(client)
        resp = client.get("/api/challenges")
        assert resp.status_code == 200
        challenges = resp.json()
        assert len(challenges) == 1
        assert challenges[0]["campus_id"] == "csub"

    def test_student_cannot_create_challenge(self, client):
        _sign_in_as(client, "student")
        resp = _create_challenge(client)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_challenge(self, client):
        resp = _create_challenge(client)
        assert resp.status_code == 401

    def test_end_before_start_rejected(self, client):
        _sign_in_as(client, "admin")
        resp = _create_challenge(client, start_date="2025-12-15", end_date="2025-09-01")
        assert resp.status_code == 422

    def test_update_challenge_attributes(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]

        resp = client.patch(
            f"/api/challenges/{challenge_id}",
            json={"name": "Spring 2026 Wellness", "semester": "Spring 2026"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Spring 2026 Wellness"
        assert body["semester"] == "Spring 2026"

    def test_cannot_see_other_campus_challenge(self, client):
        """Campus isolation: a challenge created by campus A is not visible to campus B.

        The mock IdP always resolves to campus 'csub', so we verify 404 when
        fetching a non-existent ID rather than cross-campus bleed.
        """
        _sign_in_as(client, "staff")
        resp = client.get("/api/challenges/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Publish (Gherkin: "Publish a challenge")
# ---------------------------------------------------------------------------


class TestPublishChallenge:
    def test_publish_transitions_to_published(self, client):
        _sign_in_as(client, "admin")
        challenge_id = _create_challenge(client).json()["id"]

        resp = client.post(f"/api/challenges/{challenge_id}/publish")
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    def test_double_publish_is_conflict(self, client):
        _sign_in_as(client, "admin")
        challenge_id = _create_challenge(client).json()["id"]
        client.post(f"/api/challenges/{challenge_id}/publish")

        resp = client.post(f"/api/challenges/{challenge_id}/publish")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# FR-B2 — Add ordered tasks (Gherkin: "Add ordered weekly tasks")
# ---------------------------------------------------------------------------


class TestAddTasks:
    def test_add_task_retains_all_attributes(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        resp = _add_task(client, challenge_id)

        assert resp.status_code == 201
        t = resp.json()
        assert t["title"] == "Week 1 – Vision Check"
        assert t["caption"] == "Get your eyes examined."
        assert t["activity_type"] == "health_screening"
        assert t["location"] == "SHS Lobby"
        assert t["date_window_start"] == "2025-09-01"
        assert t["date_window_end"] == "2025-09-07"
        assert t["prize"] == "Raffle entry"
        assert t["required"] is True
        assert t["position"] == 1

    def test_tasks_are_saved_in_order(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        titles = [f"Week {i}" for i in range(1, 8)]
        for title in titles:
            _add_task(client, challenge_id, title=title)

        challenge = client.get(f"/api/challenges/{challenge_id}").json()
        actual_titles = [t["title"] for t in challenge["tasks"]]
        assert actual_titles == titles

    def test_positions_are_sequential(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        for i in range(1, 4):
            _add_task(client, challenge_id, title=f"Week {i}")

        tasks = client.get(f"/api/challenges/{challenge_id}").json()["tasks"]
        assert [t["position"] for t in tasks] == [1, 2, 3]

    def test_task_date_window_end_before_start_rejected(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        resp = _add_task(
            client,
            challenge_id,
            date_window_start="2025-09-07",
            date_window_end="2025-09-01",
        )
        assert resp.status_code == 422

    def test_update_task_attribute(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        task_id = _add_task(client, challenge_id).json()["id"]

        resp = client.patch(
            f"/api/challenges/{challenge_id}/tasks/{task_id}",
            json={"caption": "Updated caption"},
        )
        assert resp.status_code == 200
        assert resp.json()["caption"] == "Updated caption"

    def test_delete_task_closes_gap(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        ids = []
        for i in range(1, 4):
            ids.append(_add_task(client, challenge_id, title=f"Week {i}").json()["id"])

        # Delete the middle task (position 2).
        resp = client.delete(f"/api/challenges/{challenge_id}/tasks/{ids[1]}")
        assert resp.status_code == 204

        tasks = client.get(f"/api/challenges/{challenge_id}").json()["tasks"]
        assert len(tasks) == 2
        assert [t["position"] for t in tasks] == [1, 2]
        assert [t["title"] for t in tasks] == ["Week 1", "Week 3"]


# ---------------------------------------------------------------------------
# FR-B2 — Reorder tasks (Gherkin: "Reorder tasks")
# ---------------------------------------------------------------------------


class TestReorderTasks:
    def _setup_challenge_with_tasks(self, client, count: int = 7):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client).json()["id"]
        task_ids = []
        for i in range(1, count + 1):
            task_ids.append(
                _add_task(client, challenge_id, title=f"Week {i}").json()["id"]
            )
        return challenge_id, task_ids

    def test_reorder_moves_week5_before_week3(self, client):
        challenge_id, ids = self._setup_challenge_with_tasks(client, 7)
        # Original: [1,2,3,4,5,6,7] by task id index
        # Move week 5 (ids[4]) before week 3 (ids[2])
        new_order = [ids[0], ids[1], ids[4], ids[2], ids[3], ids[5], ids[6]]

        resp = client.put(
            f"/api/challenges/{challenge_id}/tasks/order",
            json={"task_ids": new_order},
        )
        assert resp.status_code == 200
        returned_ids = [t["id"] for t in resp.json()]
        assert returned_ids == new_order

    def test_reorder_positions_are_1_based_sequential(self, client):
        challenge_id, ids = self._setup_challenge_with_tasks(client, 3)
        new_order = [ids[2], ids[0], ids[1]]

        resp = client.put(
            f"/api/challenges/{challenge_id}/tasks/order",
            json={"task_ids": new_order},
        )
        assert resp.status_code == 200
        positions = [t["position"] for t in resp.json()]
        assert positions == [1, 2, 3]

    def test_reorder_persists_new_order(self, client):
        challenge_id, ids = self._setup_challenge_with_tasks(client, 3)
        new_order = [ids[2], ids[0], ids[1]]
        client.put(
            f"/api/challenges/{challenge_id}/tasks/order",
            json={"task_ids": new_order},
        )

        # Re-fetch; GET must reflect the new order.
        tasks = client.get(f"/api/challenges/{challenge_id}").json()["tasks"]
        assert [t["id"] for t in tasks] == new_order

    def test_reorder_with_wrong_ids_rejected(self, client):
        challenge_id, ids = self._setup_challenge_with_tasks(client, 2)
        resp = client.put(
            f"/api/challenges/{challenge_id}/tasks/order",
            json={"task_ids": [ids[0], 99999]},  # 99999 doesn't belong here
        )
        assert resp.status_code == 422

    def test_reorder_with_duplicate_ids_rejected(self, client):
        challenge_id, ids = self._setup_challenge_with_tasks(client, 2)
        resp = client.put(
            f"/api/challenges/{challenge_id}/tasks/order",
            json={"task_ids": [ids[0], ids[0]]},
        )
        assert resp.status_code == 422
