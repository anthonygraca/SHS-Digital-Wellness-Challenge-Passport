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


def _add_item(client, challenge_id: int, task_id: int, **overrides):
    """Attach an assessment item; defaults to an MCQ."""
    payload = {
        "item_type": "mcq",
        "prompt": "How many hours of sleep are recommended?",
        "outcome_tag": "sleep_hygiene",
        "options": ["6", "7", "8", "9"],
        "answer_key": "8",
        **overrides,
    }
    return client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items", json=payload
    )


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
# FR-B4 — Theme selection (Gherkin: "Apply a theme to the student app")
# ---------------------------------------------------------------------------


class TestChallengeTheme:
    def test_theme_defaults_to_empty(self, client):
        _sign_in_as(client, "staff")
        assert _create_challenge(client).json()["theme_id"] == ""

    def test_create_with_theme_round_trips(self, client):
        _sign_in_as(client, "staff")
        resp = _create_challenge(client, theme_id="stranger-things")

        assert resp.status_code == 201
        assert resp.json()["theme_id"] == "stranger-things"
        # ...and on the list view the builder renders from.
        assert client.get("/api/challenges").json()[0]["theme_id"] == "stranger-things"

    def test_switching_theme_is_a_config_change(self, client):
        """Re-skin without a code change (NFR-6): swap the theme via PATCH alone."""
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client, theme_id="stranger-things").json()["id"]
        client.post(f"/api/challenges/{challenge_id}/publish")

        resp = client.patch(
            f"/api/challenges/{challenge_id}", json={"theme_id": "harry-potter"}
        )
        assert resp.status_code == 200
        assert resp.json()["theme_id"] == "harry-potter"
        assert resp.json()["status"] == "published"

    def test_theme_can_be_reset_to_default(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client, theme_id="stranger-things").json()["id"]

        resp = client.patch(f"/api/challenges/{challenge_id}", json={"theme_id": ""})
        assert resp.status_code == 200
        assert resp.json()["theme_id"] == ""

    def test_omitting_theme_on_update_leaves_it_alone(self, client):
        _sign_in_as(client, "staff")
        challenge_id = _create_challenge(client, theme_id="stranger-things").json()["id"]

        resp = client.patch(f"/api/challenges/{challenge_id}", json={"name": "Renamed"})
        assert resp.json()["theme_id"] == "stranger-things"


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


# ---------------------------------------------------------------------------
# FR-B6 — Duplicate prior challenge
# (Gherkin: "Duplicate creates an editable draft")
# ---------------------------------------------------------------------------


def _seed_original(client, tasks: int = 3, **overrides):
    """A published challenge with `tasks` tasks — the "prior challenge" to copy."""
    _sign_in_as(client, "staff")
    resp = _create_challenge(client, theme_id="stranger-things", **overrides)
    challenge_id = resp.json()["id"]
    task_ids = [
        _add_task(client, challenge_id, title=f"Week {i}").json()["id"]
        for i in range(1, tasks + 1)
    ]
    client.post(f"/api/challenges/{challenge_id}/publish")
    return challenge_id, task_ids


class TestDuplicateChallenge:
    def test_duplicate_creates_new_draft(self, client):
        challenge_id, _ = _seed_original(client)

        resp = client.post(f"/api/challenges/{challenge_id}/duplicate")

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["id"] != challenge_id

    def test_duplicate_copies_tasks_in_order(self, client):
        challenge_id, _ = _seed_original(client, tasks=3)

        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()

        assert [t["title"] for t in copy_body["tasks"]] == ["Week 1", "Week 2", "Week 3"]
        assert [t["position"] for t in copy_body["tasks"]] == [1, 2, 3]

    def test_duplicate_copies_all_task_attributes(self, client):
        challenge_id, _ = _seed_original(client, tasks=1)

        copy_task = client.post(f"/api/challenges/{challenge_id}/duplicate").json()[
            "tasks"
        ][0]

        assert copy_task["caption"] == "Get your eyes examined."
        assert copy_task["activity_type"] == "health_screening"
        assert copy_task["location"] == "SHS Lobby"
        assert copy_task["prize"] == "Raffle entry"
        assert copy_task["required"] is True
        # Dates come over verbatim — the admin retimes them before publishing.
        assert copy_task["date_window_start"] == "2025-09-01"
        assert copy_task["date_window_end"] == "2025-09-07"

    def test_duplicate_copies_challenge_dates_verbatim(self, client):
        challenge_id, _ = _seed_original(client, tasks=0)

        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()

        assert copy_body["start_date"] == "2025-09-01"
        assert copy_body["end_date"] == "2025-12-15"

    def test_duplicate_copies_assessment_items(self, client):
        challenge_id, task_ids = _seed_original(client, tasks=1)
        _add_item(client, challenge_id, task_ids[0])
        _add_item(
            client,
            challenge_id,
            task_ids[0],
            item_type="reflection",
            prompt="Describe your sleep routine.",
            outcome_tag="self_reflection",
            rubric="Full credit for 3+ sentences.",
            options=None,
            answer_key=None,
        )

        items = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["tasks"][
            0
        ]["assessment_items"]

        assert len(items) == 2
        mcq = next(i for i in items if i["item_type"] == "mcq")
        assert mcq["prompt"] == "How many hours of sleep are recommended?"
        assert mcq["outcome_tag"] == "sleep_hygiene"
        assert mcq["options"] == ["6", "7", "8", "9"]
        assert mcq["answer_key"] == "8"

        reflection = next(i for i in items if i["item_type"] == "reflection")
        assert reflection["prompt"] == "Describe your sleep routine."
        assert reflection["rubric"] == "Full credit for 3+ sentences."

    def test_duplicate_copies_theme(self, client):
        challenge_id, _ = _seed_original(client)

        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()

        assert copy_body["theme_id"] == "stranger-things"

    def test_duplicate_does_not_copy_enrollments(self, client, db_sessionmaker):
        """Enrollments belong to the original's run, not to the template."""
        from app.models.challenge import Enrollment
        from app.models.student import Student

        challenge_id, _ = _seed_original(client)
        with db_sessionmaker() as db:
            student = Student(
                campus_id="csub", sso_subject="s1@csub.edu", affiliation="student"
            )
            db.add(student)
            db.flush()
            db.add(Enrollment(student_id=student.id, challenge_id=challenge_id))
            db.commit()

        copy_id = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["id"]

        with db_sessionmaker() as db:
            copied = (
                db.query(Enrollment).filter(Enrollment.challenge_id == copy_id).all()
            )
            original = (
                db.query(Enrollment).filter(Enrollment.challenge_id == challenge_id).all()
            )
        assert copied == []
        assert len(original) == 1

    def test_duplicate_tasks_get_fresh_qr_tokens(self, client):
        """qr_token is derived from task id, so copies mint their own (US-8)."""
        challenge_id, _ = _seed_original(client, tasks=1)
        original_token = client.get(f"/api/challenges/{challenge_id}").json()["tasks"][0][
            "qr_token"
        ]

        copy_task = client.post(f"/api/challenges/{challenge_id}/duplicate").json()[
            "tasks"
        ][0]

        assert copy_task["qr_token"] != original_token

    # -- naming -------------------------------------------------------------

    def test_default_name_is_copy_suffixed(self, client):
        challenge_id, _ = _seed_original(client)

        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()

        assert copy_body["name"] == "Fall 2025 Wellness (Copy)"
        assert copy_body["semester"] == "Fall 2025"

    def test_duplicate_accepts_name_and_semester_override(self, client):
        challenge_id, _ = _seed_original(client)

        resp = client.post(
            f"/api/challenges/{challenge_id}/duplicate",
            json={"name": "Spring 2026 Wellness", "semester": "Spring 2026"},
        )

        assert resp.status_code == 201
        assert resp.json()["name"] == "Spring 2026 Wellness"
        assert resp.json()["semester"] == "Spring 2026"

    def test_repeated_duplication_increments_suffix(self, client):
        challenge_id, _ = _seed_original(client)

        first = client.post(f"/api/challenges/{challenge_id}/duplicate").json()
        second = client.post(f"/api/challenges/{challenge_id}/duplicate").json()

        assert first["name"] == "Fall 2025 Wellness (Copy)"
        assert second["name"] == "Fall 2025 Wellness (Copy 2)"

    def test_duplicating_a_copy_does_not_stack_suffixes(self, client):
        challenge_id, _ = _seed_original(client)
        copy_id = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["id"]

        second = client.post(f"/api/challenges/{copy_id}/duplicate").json()

        assert second["name"] == "Fall 2025 Wellness (Copy 2)"

    def test_duplicate_with_colliding_explicit_name_is_conflict(self, client):
        challenge_id, _ = _seed_original(client)

        resp = client.post(
            f"/api/challenges/{challenge_id}/duplicate",
            json={"name": "Fall 2025 Wellness", "semester": "Fall 2025"},
        )

        assert resp.status_code == 409

    def test_same_name_in_a_different_semester_is_allowed(self, client):
        challenge_id, _ = _seed_original(client)

        resp = client.post(
            f"/api/challenges/{challenge_id}/duplicate",
            json={"name": "Fall 2025 Wellness", "semester": "Spring 2026"},
        )

        assert resp.status_code == 201

    # -- auth guards --------------------------------------------------------

    def test_student_cannot_duplicate(self, client):
        challenge_id, _ = _seed_original(client)
        client.post("/auth/logout")
        _sign_in_as(client, "student")

        resp = client.post(f"/api/challenges/{challenge_id}/duplicate")
        assert resp.status_code == 403

    def test_unauthenticated_cannot_duplicate(self, client):
        challenge_id, _ = _seed_original(client)
        client.post("/auth/logout")

        resp = client.post(f"/api/challenges/{challenge_id}/duplicate")
        assert resp.status_code == 401

    def test_duplicate_unknown_challenge_is_404(self, client):
        """Also covers cross-campus: get_challenge filters on campus_id, so another
        campus's ID is indistinguishable from one that does not exist."""
        _sign_in_as(client, "staff")

        resp = client.post("/api/challenges/99999/duplicate")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# FR-B6 — Duplicate prior challenge
# (Gherkin: "Editing the copy does not affect the original")
# ---------------------------------------------------------------------------


class TestCopyIsIndependent:
    def test_editing_task_in_copy_leaves_original_unchanged(self, client):
        challenge_id, _ = _seed_original(client, tasks=3)
        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()
        copy_id, copy_task_id = copy_body["id"], copy_body["tasks"][0]["id"]

        client.patch(
            f"/api/challenges/{copy_id}/tasks/{copy_task_id}",
            json={"title": "Week 1 – Rewritten"},
        )

        original_tasks = client.get(f"/api/challenges/{challenge_id}").json()["tasks"]
        assert original_tasks[0]["title"] == "Week 1"

    def test_editing_mcq_options_in_copy_leaves_original_unchanged(self, client):
        challenge_id, task_ids = _seed_original(client, tasks=1)
        original_item_id = _add_item(client, challenge_id, task_ids[0]).json()["id"]

        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()
        copy_id = copy_body["id"]
        copy_task_id = copy_body["tasks"][0]["id"]
        copy_item_id = copy_body["tasks"][0]["assessment_items"][0]["id"]

        client.patch(
            f"/api/challenges/{copy_id}/tasks/{copy_task_id}/items/{copy_item_id}",
            json={"options": ["1", "2", "3", "4"], "answer_key": "4"},
        )

        original_item = client.get(
            f"/api/challenges/{challenge_id}/tasks/{task_ids[0]}/items"
        ).json()
        assert original_item[0]["id"] == original_item_id
        assert original_item[0]["options"] == ["6", "7", "8", "9"]
        assert original_item[0]["answer_key"] == "8"

    def test_deleting_task_in_copy_leaves_original_unchanged(self, client):
        challenge_id, _ = _seed_original(client, tasks=3)
        copy_body = client.post(f"/api/challenges/{challenge_id}/duplicate").json()
        copy_id = copy_body["id"]

        client.delete(f"/api/challenges/{copy_id}/tasks/{copy_body['tasks'][1]['id']}")

        original_tasks = client.get(f"/api/challenges/{challenge_id}").json()["tasks"]
        assert [t["title"] for t in original_tasks] == ["Week 1", "Week 2", "Week 3"]
        assert [t["position"] for t in original_tasks] == [1, 2, 3]

    def test_adding_task_to_copy_leaves_original_unchanged(self, client):
        challenge_id, _ = _seed_original(client, tasks=3)
        copy_id = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["id"]

        _add_task(client, copy_id, title="Week 4 – New")

        assert len(client.get(f"/api/challenges/{challenge_id}").json()["tasks"]) == 3
        assert len(client.get(f"/api/challenges/{copy_id}").json()["tasks"]) == 4

    def test_publishing_copy_leaves_original_status_unchanged(self, client):
        challenge_id, _ = _seed_original(client)
        copy_id = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["id"]

        client.post(f"/api/challenges/{copy_id}/publish")

        original = client.get(f"/api/challenges/{challenge_id}").json()
        assert original["status"] == "published"
        assert client.get(f"/api/challenges/{copy_id}").json()["status"] == "published"

    def test_renaming_copy_leaves_original_unchanged(self, client):
        challenge_id, _ = _seed_original(client)
        copy_id = client.post(f"/api/challenges/{challenge_id}/duplicate").json()["id"]

        client.patch(f"/api/challenges/{copy_id}", json={"name": "Renamed Copy"})

        assert client.get(f"/api/challenges/{challenge_id}").json()["name"] == (
            "Fall 2025 Wellness"
        )
