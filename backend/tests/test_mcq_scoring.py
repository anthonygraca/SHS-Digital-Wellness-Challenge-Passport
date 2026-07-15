"""Edge cases for FR-E4 — MCQ auto-scoring (US-18).

The two Gherkin scenarios themselves are executed by test_mcq_scoring_bdd.py against
tests/features/mcq_scoring.feature. This module covers what the scenarios leave
implicit: the auth guards, campus isolation, the answer-key leak the student surface
exists to prevent, and the submissions that must be refused rather than scored.

Two of these carry more weight than their size suggests. "An unknown option writes
nothing" and "a second submission leaves the first score untouched" are what make the
one-attempt constraint mean something; without them it is decorative, and the FR-E4
feedback could not safely name the correct option.
"""

from __future__ import annotations

from datetime import date

from app.models.challenge import AssessmentItem, AssessmentResponse, Challenge, Task

ADMIN = "admin@csub.edu"
STUDENT = "s1@csub.edu"

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

RUBRIC = "Mentions at least two habits and why they matter."


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_participation_report.py)
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _items_url(week_no: int) -> str:
    return f"/api/assessments/weeks/{week_no}/items"


def _submit_url(item_id: int) -> str:
    return f"/api/assessments/items/{item_id}/responses"


def _add_item(client, challenge_id: int, task_id: int, **over) -> dict:
    payload = {
        "item_type": "mcq",
        "prompt": PROMPT,
        "outcome_tag": OUTCOME_TAG,
        "options": OPTIONS,
        "answer_key": CORRECT,
        **over,
    }
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items", json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup(client, *, publish: bool = True, weeks: int = 1) -> dict:
    """A challenge with `weeks` weeks, an MCQ on week 1, and a signed-in student.

    Leaves the caller on a *student* session. Enrolling mints the Student row that a
    stored response is foreign-keyed to.
    """
    _sign_in_as(client, "staff", ADMIN)
    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
    ).json()
    task_ids = [
        client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": f"Week {n}", "required": True},
        ).json()["id"]
        for n in range(1, weeks + 1)
    ]
    item = _add_item(client, challenge["id"], task_ids[0])
    if publish:
        client.post(f"/api/challenges/{challenge['id']}/publish")

    _sign_in_as(client, "student", STUDENT)
    client.post("/enrollment")
    return {
        "challenge_id": challenge["id"],
        "task_ids": task_ids,
        "item_id": item["id"],
    }


# ---------------------------------------------------------------------------
# Auth guards (US-2 / FR-A3)
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_anonymous_cannot_list_items(self, client):
        setup = _setup(client)
        client.cookies.clear()
        assert client.get(_items_url(1)).status_code == 401
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 401
        )

    def test_non_current_student_is_forbidden(self, client):
        setup = _setup(client)
        _sign_in_as(client, "alum", "grad@csub.edu")

        listed = client.get(_items_url(1))
        assert listed.status_code == 403
        assert listed.json()["detail"]["code"] == "not_current_student"

        submitted = client.post(_submit_url(setup["item_id"]), json={"answer": CORRECT})
        assert submitted.status_code == 403

    def test_admin_session_is_not_a_student_session(self, client):
        """Staff are not current students, so the student surface refuses them too.

        Admins read items through the admin route, which is where the answer key lives.
        """
        setup = _setup(client)
        _sign_in_as(client, "staff", ADMIN)
        assert client.get(_items_url(1)).status_code == 403
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 403
        )


# ---------------------------------------------------------------------------
# The answer key must not reach the student surface
# ---------------------------------------------------------------------------


class TestAnswerKeyIsNotLeaked:
    def test_listing_items_never_carries_the_answer_key(self, client):
        """The whole of FR-E4 rests on this: a leaked key makes auto-scoring theatre.

        The correct option's *text* is necessarily in the body — it is one of the four
        the student chooses between. What must not be there is anything identifying it
        as the right one. So this asserts on the shape: no key-bearing field, and the
        options arriving as a flat list of equals in their authored order.

        Checked against the raw text as well as the parsed object, so a key smuggled
        under another name — or a `rubric` riding along on a future reflection — fails
        here too.
        """
        _setup(client)
        resp = client.get(_items_url(1))
        assert resp.status_code == 200

        body = resp.text
        assert "answer_key" not in body
        assert "answerKey" not in body
        assert "correctOption" not in body
        assert "rubric" not in body

        item = resp.json()
        assert list(item[0]["options"]) == OPTIONS, "authored order, nothing reordered"
        assert item[0]["outcomeTag"] == OUTCOME_TAG
        # Nothing beyond the agreed student-facing surface.
        assert set(item[0]) == {
            "id",
            "weekNo",
            "prompt",
            "outcomeTag",
            "options",
            "yourResponse",
        }

    def test_the_key_is_revealed_only_once_the_item_is_closed(self, client):
        """correctOption comes back with the result — after one-attempt has closed it."""
        setup = _setup(client)
        result = client.post(_submit_url(setup["item_id"]), json={"answer": INCORRECT})
        assert result.status_code == 201
        assert result.json()["correctOption"] == CORRECT


# ---------------------------------------------------------------------------
# Campus isolation and challenge visibility
# ---------------------------------------------------------------------------


class TestIsolationAndVisibility:
    def test_another_campus_item_is_not_found(self, client, db_sessionmaker):
        """A foreign item is 404, not 403 — existence is not the student's to learn."""
        _setup(client)

        # The mock IdP always resolves to campus_id="csub", so a rival campus's data
        # can only be created directly.
        with db_sessionmaker() as db:
            rival = Challenge(
                campus_id="other",
                name="Rival Challenge",
                semester="Fall 2025",
                start_date=date(2026, 1, 1),  # would win "most recent" if unscoped
                end_date=date(2026, 5, 1),
                status="published",
            )
            db.add(rival)
            db.flush()
            rival_task = Task(challenge_id=rival.id, position=1, title="Rival Week 1")
            db.add(rival_task)
            db.flush()
            rival_item = AssessmentItem(
                task_id=rival_task.id,
                item_type="mcq",
                prompt="Rival question",
                outcome_tag="rival-tag",
                options=OPTIONS,
                answer_key=CORRECT,
            )
            db.add(rival_item)
            db.commit()
            rival_item_id = rival_item.id

        resp = client.post(_submit_url(rival_item_id), json={"answer": CORRECT})
        assert resp.status_code == 404

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 0

    def test_draft_challenge_item_is_not_found(self, client):
        """An unpublished challenge is invisible to students, items included."""
        setup = _setup(client, publish=False)
        assert client.get(_items_url(1)).status_code == 404
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 404
        )

    def test_unknown_item_is_not_found(self, client):
        _setup(client)
        assert (
            client.post(_submit_url(999_999), json={"answer": CORRECT}).status_code == 404
        )

    def test_unknown_week_is_not_found(self, client):
        _setup(client, weeks=1)
        assert client.get(_items_url(99)).status_code == 404

    def test_week_without_items_is_empty_not_missing(self, client):
        """A week with no knowledge check is the common case, not an error."""
        _setup(client, weeks=2)
        resp = client.get(_items_url(2))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Submissions that must be refused rather than scored
# ---------------------------------------------------------------------------


class TestRefusedSubmissions:
    def test_unknown_option_is_rejected_and_writes_nothing(self, client, db_sessionmaker):
        """Refused, not scored 0.0.

        Scoring a bogus answer would burn the student's single attempt on a client bug
        or a tampered payload, with no way back past the unique constraint.
        """
        setup = _setup(client)
        resp = client.post(_submit_url(setup["item_id"]), json={"answer": "Beer"})
        assert resp.status_code == 400

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 0

        # And the attempt is still available.
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 201
        )

    def test_reflection_item_is_rejected(self, client):
        """A reflection has no answer key; comparing against NULL would score it 0.0.

        US-19 (FR-E5) owns rubric scoring — this path must not silently fail it.
        """
        _sign_in_as(client, "staff", ADMIN)
        challenge = client.post(
            "/api/challenges",
            json={
                "name": "Fall 2025 Wellness",
                "semester": "Fall 2025",
                "start_date": "2025-09-01",
                "end_date": "2025-12-15",
            },
        ).json()
        task = client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": "Week 1", "required": True},
        ).json()
        item = _add_item(
            client,
            challenge["id"],
            task["id"],
            item_type="reflection",
            rubric=RUBRIC,
            options=None,
            answer_key=None,
        )
        client.post(f"/api/challenges/{challenge['id']}/publish")

        _sign_in_as(client, "student", STUDENT)
        client.post("/enrollment")

        resp = client.post(_submit_url(item["id"]), json={"answer": "I sleep well."})
        assert resp.status_code == 400

    def test_reflection_items_are_not_listed(self, client):
        """US-18 has no way to render or score one, so it does not offer one."""
        _sign_in_as(client, "staff", ADMIN)
        challenge = client.post(
            "/api/challenges",
            json={
                "name": "Fall 2025 Wellness",
                "semester": "Fall 2025",
                "start_date": "2025-09-01",
                "end_date": "2025-12-15",
            },
        ).json()
        task = client.post(
            f"/api/challenges/{challenge['id']}/tasks",
            json={"title": "Week 1", "required": True},
        ).json()
        _add_item(client, challenge["id"], task["id"])
        _add_item(
            client,
            challenge["id"],
            task["id"],
            item_type="reflection",
            prompt="What changed for you?",
            rubric=RUBRIC,
            options=None,
            answer_key=None,
        )
        client.post(f"/api/challenges/{challenge['id']}/publish")

        _sign_in_as(client, "student", STUDENT)
        client.post("/enrollment")

        items = client.get(_items_url(1)).json()
        assert [i["prompt"] for i in items] == [PROMPT]


# ---------------------------------------------------------------------------
# One attempt per item
# ---------------------------------------------------------------------------


class TestOneAttempt:
    def test_resubmitting_conflicts_and_leaves_the_score_untouched(
        self, client, db_sessionmaker
    ):
        """The reason the FR-E4 feedback can safely name the correct option.

        Without this, "answer wrong, read the answer, answer again" would make every
        stored score a 1.0 and FR-F4's per-outcome report a flat line.
        """
        setup = _setup(client)
        first = client.post(_submit_url(setup["item_id"]), json={"answer": INCORRECT})
        assert first.status_code == 201
        assert first.json()["score"] == 0.0

        second = client.post(_submit_url(setup["item_id"]), json={"answer": CORRECT})
        assert second.status_code == 409

        with db_sessionmaker() as db:
            rows = db.query(AssessmentResponse).all()
            assert len(rows) == 1
            assert rows[0].score == 0.0
            assert rows[0].response == INCORRECT

    def test_another_student_is_unaffected_by_the_first_students_attempt(self, client):
        """The constraint is per student, not per item."""
        setup = _setup(client)
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 201
        )

        _sign_in_as(client, "student", "s2@csub.edu")
        client.post("/enrollment")
        assert (
            client.post(
                _submit_url(setup["item_id"]), json={"answer": CORRECT}
            ).status_code
            == 201
        )

    def test_a_students_stored_answer_is_their_own(self, client):
        """yourResponse is scoped to the caller, not the last person to answer."""
        setup = _setup(client)
        client.post(_submit_url(setup["item_id"]), json={"answer": INCORRECT})

        _sign_in_as(client, "student", "s2@csub.edu")
        client.post("/enrollment")
        assert client.get(_items_url(1)).json()[0]["yourResponse"] is None

        _sign_in_as(client, "student", STUDENT)
        assert client.get(_items_url(1)).json()[0]["yourResponse"]["score"] == 0.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_correct_and_incorrect_persist_exact_scores(self, client, db_sessionmaker):
        """1.0 / 0.0 in the column itself — FR-F4 will average these."""
        setup = _setup(client)
        client.post(_submit_url(setup["item_id"]), json={"answer": CORRECT})

        with db_sessionmaker() as db:
            row = db.query(AssessmentResponse).one()
            assert row.score == 1.0
            assert row.response == CORRECT
            assert row.scored_by == "auto"

    def test_the_outcome_tag_follows_the_item_when_retagged(self, client):
        """Why the tag is joined rather than copied onto the response.

        An admin retagging an item (US-12) retags its whole score history, which is
        what retagging means — a copied tag would leave this answer filed under the
        old one and split FR-F4's aggregate across both.
        """
        setup = _setup(client)
        client.post(_submit_url(setup["item_id"]), json={"answer": CORRECT})

        _sign_in_as(client, "staff", ADMIN)
        retag = client.patch(
            f"/api/challenges/{setup['challenge_id']}/tasks/{setup['task_ids'][0]}"
            f"/items/{setup['item_id']}",
            json={"outcome_tag": "eye-health"},
        )
        assert retag.status_code == 200, retag.text

        _sign_in_as(client, "student", STUDENT)
        item = client.get(_items_url(1)).json()[0]
        assert item["outcomeTag"] == "eye-health"
        assert item["yourResponse"]["score"] == 1.0
