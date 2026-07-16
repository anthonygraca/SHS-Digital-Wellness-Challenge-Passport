"""Edge cases for the FR-E5 student surface — reflection scoring (US-19).

The two Gherkin scenarios are executed by test_reflection_scoring_bdd.py; the admin
override's edges live in test_reflection_override.py; the stub scorer's own behaviour is
unit-tested in test_reflection_scorer.py. This module covers what the scenarios leave
implicit: the auth guards, campus isolation, the rubric leak the student surface exists
to prevent, the submissions that must be refused, and what happens when the scorer cannot
answer.

Three of these carry more weight than their size suggests. "The rubric never reaches the
student" is the FR-E5 counterpart of FR-E4's answer-key test, and it matters more here
than there: the stub scorer rewards quoting the rubric back, so a leaked rubric is not
merely a spoiler, it is the mark scheme and the exploit at once. And the pair
"a scorer failure stores nothing" / "the item is still answerable afterwards" are what
make a one-attempt reflection safe to fail — without the second, the first is a claim
about a row count that no student can feel.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.challenge import AssessmentItem, AssessmentResponse, Challenge, Task
from app.services.reflection_scoring import (
    ReflectionScore,
    ScoringUnavailable,
    get_reflection_scorer,
)

ADMIN = "admin@csub.edu"
STUDENT = "s1@csub.edu"

PROMPT = "What is one number from today's labs you want to change, and how?"
OUTCOME_TAG = "know-your-numbers"
RUBRIC = "Names a specific number; names a specific doable action; connects the two."

REFLECTION = (
    "My blood pressure was higher than I expected. I am going to walk for twenty "
    "minutes after dinner and recheck the number next month."
)

MCQ_PROMPT = "How often should a healthy adult have a comprehensive eye exam?"
MCQ_OPTIONS = ["Every 1-2 years", "Once, when I turn 18"]
MCQ_CORRECT = "Every 1-2 years"


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_mcq_scoring.py)
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _items_url(week_no: int) -> str:
    return f"/api/assessments/weeks/{week_no}/items"


def _submit_url(item_id: int) -> str:
    return f"/api/assessments/items/{item_id}/reflections"


def _submit(client, item_id: int, text: str = REFLECTION):
    return client.post(_submit_url(item_id), json={"text": text})


def _add_item(client, challenge_id: int, task_id: int, **over) -> dict:
    payload = {
        "item_type": "reflection",
        "prompt": PROMPT,
        "outcome_tag": OUTCOME_TAG,
        "rubric": RUBRIC,
        **over,
    }
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items", json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup(client, *, publish: bool = True, with_mcq: bool = False) -> dict:
    """A challenge with a reflection on week 1, and a signed-in enrolled student."""
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

    mcq = None
    if with_mcq:
        mcq = _add_item(
            client,
            challenge["id"],
            task["id"],
            item_type="mcq",
            prompt=MCQ_PROMPT,
            options=MCQ_OPTIONS,
            answer_key=MCQ_CORRECT,
            rubric=None,
        )
    item = _add_item(client, challenge["id"], task["id"])

    if publish:
        assert (
            client.post(f"/api/challenges/{challenge['id']}/publish").status_code == 200
        )

    _sign_in_as(client, "student", STUDENT)
    client.post("/enrollment")

    return {
        "challenge_id": challenge["id"],
        "task_id": task["id"],
        "item_id": item["id"],
        "mcq_id": mcq["id"] if mcq else None,
    }


class _RaisingScorer:
    """Stands in for a model that is down, timing out, or refusing."""

    def score(self, *, prompt, rubric, outcome_tag, response):
        raise ScoringUnavailable("provider is down")


class _OutOfRangeScorer:
    """Stands in for a model that answers, but not with a usable number."""

    def __init__(self, score: float = 1.4):
        self._score = score

    def score(self, *, prompt, rubric, outcome_tag, response):
        return ReflectionScore(score=self._score, feedback="Nice work.")


@pytest.fixture
def broken_scorer(client):
    """Swap the scorer for one that always fails.

    Via dependency_overrides rather than monkeypatch — the same seam conftest already
    uses for get_db, and the reason score_reflection takes its scorer as a parameter.
    The client fixture clears overrides on teardown.
    """
    from app.main import app

    app.dependency_overrides[get_reflection_scorer] = lambda: _RaisingScorer()
    yield
    app.dependency_overrides.pop(get_reflection_scorer, None)


# ---------------------------------------------------------------------------
# The rubric is not the student's to see
# ---------------------------------------------------------------------------


class TestRubricIsNotLeaked:
    def test_listing_items_never_carries_the_rubric(self, client):
        """FR-E5's counterpart to the FR-E4 answer-key test, and a sharper case.

        A rubric is not just a spoiler: the stub scorer rewards vocabulary overlap, so
        handing a student the rubric hands them both the mark scheme and the highest-
        scoring way to game it. Asserted on the raw text as well as the parsed object,
        so a rubric smuggled under another name fails here too.
        """
        _setup(client)
        resp = client.get(_items_url(1))
        assert resp.status_code == 200

        body = resp.text
        assert "rubric" not in body
        assert "answer_key" not in body
        assert "answerKey" not in body
        assert RUBRIC not in body

        item = resp.json()[0]
        assert set(item) == {
            "id",
            "weekNo",
            "itemType",
            "prompt",
            "outcomeTag",
            "options",
            "yourResponse",
        }

    def test_the_scoring_result_never_carries_the_rubric(self, client):
        """The rubric must not arrive with the score either — one attempt, so it is
        useless to the student and still the mark scheme."""
        setup = _setup(client)
        resp = client.post(_submit_url(setup["item_id"]), json={"text": REFLECTION})
        assert resp.status_code == 201

        assert "rubric" not in resp.text
        assert RUBRIC not in resp.text
        assert set(resp.json()) == {
            "itemId",
            "outcomeTag",
            "score",
            "scoredBy",
            "feedback",
        }


# ---------------------------------------------------------------------------
# Both item types now share the week surface
# ---------------------------------------------------------------------------


class TestBothItemTypesAreListed:
    def test_a_reflection_is_listed_with_its_item_type(self, client):
        """The filter US-18 needed is gone: FR-E5 gives reflections a surface."""
        _setup(client)
        items = client.get(_items_url(1)).json()

        assert [i["prompt"] for i in items] == [PROMPT]
        assert items[0]["itemType"] == "reflection"
        assert items[0]["options"] == [], "a reflection has nothing to choose between"

    def test_an_mcq_and_a_reflection_on_one_week_are_both_listed(self, client):
        """The mockup puts both cards on one screen, so one week must serve both."""
        _setup(client, with_mcq=True)
        items = client.get(_items_url(1)).json()

        assert {i["itemType"] for i in items} == {"mcq", "reflection"}
        assert len(items) == 2

    def test_a_stored_reflection_has_no_correct_and_carries_feedback(self, client):
        """The bug the nullable `correct` exists to prevent.

        A reflection scoring 0.6 is neither right nor wrong, and `correct: false` would
        render as "Incorrect" — a verdict the item cannot support. Its feedback, unlike
        an MCQ's, is stored and so survives a reload.
        """
        setup = _setup(client)
        result = client.post(
            _submit_url(setup["item_id"]), json={"text": REFLECTION}
        ).json()

        stored = client.get(_items_url(1)).json()[0]["yourResponse"]
        assert stored["correct"] is None
        assert stored["feedback"] == result["feedback"]
        assert stored["scoredBy"] == "auto"

    def test_a_stored_mcq_has_no_feedback(self, client):
        """The other half of the asymmetry: MCQ feedback is composed from the answer key
        at scoring time and never stored, so a revisit cannot restate it."""
        setup = _setup(client, with_mcq=True)
        client.post(
            f"/api/assessments/items/{setup['mcq_id']}/responses",
            json={"answer": MCQ_CORRECT},
        )

        items = client.get(_items_url(1)).json()
        mcq = next(i for i in items if i["itemType"] == "mcq")
        assert mcq["yourResponse"]["feedback"] is None
        assert mcq["yourResponse"]["correct"] is True


# ---------------------------------------------------------------------------
# Submissions that must be refused rather than scored
# ---------------------------------------------------------------------------


class TestRefusedSubmissions:
    def test_submitting_a_reflection_to_an_mcq_is_400(self, client):
        setup = _setup(client, with_mcq=True)
        resp = client.post(_submit_url(setup["mcq_id"]), json={"text": REFLECTION})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "That item is not a reflection"

    def test_answering_a_reflection_via_the_mcq_route_is_400(self, client):
        """FR-E4 regression: the MCQ path still refuses reflections rather than scoring
        every one of them zero against a NULL answer key."""
        setup = _setup(client)
        resp = client.post(
            f"/api/assessments/items/{setup['item_id']}/responses",
            json={"answer": "anything"},
        )
        assert resp.status_code == 400

    def test_a_reflection_with_no_rubric_is_400_and_writes_nothing(
        self, client, db_sessionmaker
    ):
        """Refused, not scored against nothing.

        ``ReflectionCreate.rubric`` is a required str and the update path excludes None,
        so the admin API cannot produce this item — the row is built directly here
        because that is the only way it exists. The guard is still load-bearing: the
        column is nullable (one table serves both item types), seed.py constructs
        AssessmentItem without going through a schema, and rubric is exactly the kind of
        field a later "make it optional" would loosen. Without the guard a NULL rubric
        reaches the scorer and crashes it — a 500 on a student's one attempt, where this
        is a 400 that stores nothing. Same category as score_mcq's answer_key guard.
        """
        setup = _setup(client)
        with db_sessionmaker() as db:
            item = db.get(AssessmentItem, setup["item_id"])
            item.rubric = None
            db.commit()

        resp = client.post(_submit_url(setup["item_id"]), json={"text": REFLECTION})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "That item is not a reflection"

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 0

    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    def test_a_blank_reflection_is_422(self, client, text):
        """min_length alone would accept "   ", spending the one attempt on nothing."""
        setup = _setup(client)
        resp = client.post(_submit_url(setup["item_id"]), json={"text": text})
        assert resp.status_code == 422

    def test_an_overlong_reflection_is_422_and_never_reaches_the_scorer(self, client):
        """The cap is a schema concern so it 422s before the route body runs — once a
        real model is behind the seam, this is also the token bill."""
        setup = _setup(client)
        resp = client.post(_submit_url(setup["item_id"]), json={"text": "x" * 4001})
        assert resp.status_code == 422

    def test_a_second_reflection_is_409(self, client, db_sessionmaker):
        """One attempt, like an MCQ — and the first score stands."""
        setup = _setup(client)
        first = client.post(
            _submit_url(setup["item_id"]), json={"text": REFLECTION}
        ).json()

        resp = client.post(
            _submit_url(setup["item_id"]), json={"text": "A completely different take."}
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "You already submitted this reflection"

        with db_sessionmaker() as db:
            rows = db.query(AssessmentResponse).all()
            assert len(rows) == 1
            assert rows[0].score == first["score"]
            assert rows[0].response == REFLECTION


# ---------------------------------------------------------------------------
# When the scorer cannot answer
# ---------------------------------------------------------------------------


class TestScorerFailure:
    def test_a_scorer_failure_is_503_and_stores_nothing(
        self, client, db_sessionmaker, broken_scorer
    ):
        """The one 503 in the app. Nothing is written, because db.add sits after the
        scorer call — the ordering is the guarantee, not a promise in a comment."""
        setup = _setup(client)
        resp = client.post(_submit_url(setup["item_id"]), json={"text": REFLECTION})

        assert resp.status_code == 503
        assert "Nothing was recorded" in resp.json()["detail"]

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 0

    def test_the_reflection_is_still_answerable_after_a_503(
        self, client, db_sessionmaker
    ):
        """What makes "stores nothing" mean something to a student rather than to a row
        count. A one-attempt item that ate the attempt on an outage would be worse than
        one that refused."""
        from app.main import app

        setup = _setup(client)

        app.dependency_overrides[get_reflection_scorer] = lambda: _RaisingScorer()
        assert _submit(client, setup["item_id"]).status_code == 503
        app.dependency_overrides.pop(get_reflection_scorer, None)

        retry = _submit(client, setup["item_id"])
        assert retry.status_code == 201, "the outage burned the student's one attempt"

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 1

    def test_an_out_of_range_score_is_503_and_stores_nothing(
        self, client, db_sessionmaker
    ):
        """Refused, not clamped. A scorer returning 1.4 is broken; clamping to 1.0 would
        invent a grade and skew the FR-F4 mean with a number that looks legitimate."""
        from app.main import app

        setup = _setup(client)
        app.dependency_overrides[get_reflection_scorer] = lambda: _OutOfRangeScorer(1.4)
        try:
            resp = client.post(_submit_url(setup["item_id"]), json={"text": REFLECTION})
            assert resp.status_code == 503
            with db_sessionmaker() as db:
                assert db.query(AssessmentResponse).count() == 0
        finally:
            app.dependency_overrides.pop(get_reflection_scorer, None)

    def test_a_negative_score_is_also_refused(self, client, db_sessionmaker):
        from app.main import app

        setup = _setup(client)
        app.dependency_overrides[get_reflection_scorer] = lambda: _OutOfRangeScorer(-0.1)
        try:
            assert _submit(client, setup["item_id"]).status_code == 503
            with db_sessionmaker() as db:
                assert db.query(AssessmentResponse).count() == 0
        finally:
            app.dependency_overrides.pop(get_reflection_scorer, None)


# ---------------------------------------------------------------------------
# Auth + campus isolation
# ---------------------------------------------------------------------------


class TestAccess:
    def test_unauthenticated_submit_is_401(self, client):
        setup = _setup(client)
        client.cookies.clear()
        assert _submit(client, setup["item_id"]).status_code == 401

    def test_a_non_student_submit_is_403(self, client):
        setup = _setup(client)
        _sign_in_as(client, "staff", ADMIN)
        assert _submit(client, setup["item_id"]).status_code == 403

    def test_a_draft_challenge_reflection_is_404(self, client):
        """An unpublished challenge is invisible to students, reflections included."""
        setup = _setup(client, publish=False)
        assert _submit(client, setup["item_id"]).status_code == 404

    def test_another_campus_reflection_is_404(self, client, db_sessionmaker):
        """Foreign is 404, not 403 — existence is not the student's to learn."""
        _setup(client)

        # The mock IdP always resolves to campus_id="csub", so a rival campus's data can
        # only be created directly.
        with db_sessionmaker() as db:
            rival = Challenge(
                campus_id="other",
                name="Rival Challenge",
                semester="Fall 2025",
                start_date=date(2026, 1, 1),
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
                item_type="reflection",
                prompt="Rival prompt",
                outcome_tag="rival-tag",
                rubric=RUBRIC,
            )
            db.add(rival_item)
            db.commit()
            rival_item_id = rival_item.id

        resp = client.post(_submit_url(rival_item_id), json={"text": REFLECTION})
        assert resp.status_code == 404

        with db_sessionmaker() as db:
            assert db.query(AssessmentResponse).count() == 0
