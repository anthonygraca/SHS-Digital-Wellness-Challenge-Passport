"""Edge cases for the FR-E5 admin score override (US-19).

The "admin overrides an AI score" scenario itself is executed by
test_reflection_scoring_bdd.py; this module covers the guards around it: RBAC, campus
isolation, the score bounds, and what the override must leave alone.

Two of these earn their place. "The override keeps ai_feedback" pins the one decision
here that is easy to reverse by accident and impossible to undo afterwards — FR-E5
warrants no audit table, so that field beside scored_by="human" is the only trace an
override leaves. And "an admin can read responses on a draft challenge" is the entire
reason these routes hang off the challenge/task/item chain instead of reusing the
student-side lookup, which is scoped to the published challenge.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.challenge import AssessmentItem, Challenge, Task

ADMIN = "admin@csub.edu"
OTHER_ADMIN = "dean@csub.edu"
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
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _responses_url(setup: dict) -> str:
    return (
        f"/api/challenges/{setup['challenge_id']}/tasks/{setup['task_id']}"
        f"/items/{setup['item_id']}/responses"
    )


@pytest.fixture
def scored(client) -> dict:
    """A published reflection, submitted and auto-scored, left on an *admin* session."""
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
    item = client.post(
        f"/api/challenges/{challenge['id']}/tasks/{task['id']}/items",
        json={
            "item_type": "reflection",
            "prompt": PROMPT,
            "outcome_tag": OUTCOME_TAG,
            "rubric": RUBRIC,
        },
    ).json()
    client.post(f"/api/challenges/{challenge['id']}/publish")

    _sign_in_as(client, "student", STUDENT)
    client.post("/enrollment")
    result = client.post(
        f"/api/assessments/items/{item['id']}/reflections", json={"text": REFLECTION}
    ).json()

    _sign_in_as(client, "staff", ADMIN)
    setup = {
        "challenge_id": challenge["id"],
        "task_id": task["id"],
        "item_id": item["id"],
        "result": result,
    }
    setup["response_id"] = client.get(_responses_url(setup)).json()[0]["id"]
    return setup


# ---------------------------------------------------------------------------
# The override itself
# ---------------------------------------------------------------------------


class TestOverride:
    def test_it_sets_the_score_and_marks_it_human(self, client, scored):
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.25}
        )
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["score"] == 0.25
        assert body["scored_by"] == "human"

    def test_it_keeps_the_feedback_the_machine_gave(self, client, scored):
        """The decision this branch is most likely to reverse by accident.

        FR-E5 mandates no audit table, so ai_feedback beside scored_by="human" is the
        only trace an override leaves. The two answer different questions — whether the
        score is the machine's, and what the machine had said — and clearing the second
        destroys the only record of the thing being overridden. The student has already
        read it, too.
        """
        before = scored["result"]["feedback"]
        assert before

        body = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.25}
        ).json()

        assert body["ai_feedback"] == before

    def test_it_leaves_the_students_words_alone(self, client, scored):
        """An override corrects a score, not a reflection."""
        body = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.9}
        ).json()
        assert body["response"] == REFLECTION

    def test_it_is_visible_to_the_student(self, client, scored):
        """The point of the whole feature: the corrected score is the one they see."""
        client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.25}
        )

        _sign_in_as(client, "student", STUDENT)
        stored = client.get("/api/assessments/weeks/1/items").json()[0]["yourResponse"]
        assert stored["score"] == 0.25
        assert stored["scoredBy"] == "human"

    def test_overriding_twice_keeps_the_last_score(self, client, scored):
        """An override is a correction to the one row, not a new opinion beside it."""
        url = f"{_responses_url(scored)}/{scored['response_id']}"
        client.patch(url, json={"score": 0.25})
        client.patch(url, json={"score": 0.75})

        rows = client.get(_responses_url(scored)).json()
        assert len(rows) == 1
        assert rows[0]["score"] == 0.75
        assert rows[0]["scored_by"] == "human"

    def test_an_mcq_score_can_be_overridden_too(self, client):
        """Item-type-agnostic on purpose: an admin repairing scores after a bad answer
        key is a real need, and FR-E5 supplies no reason to refuse it."""
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
        item = client.post(
            f"/api/challenges/{challenge['id']}/tasks/{task['id']}/items",
            json={
                "item_type": "mcq",
                "prompt": MCQ_PROMPT,
                "outcome_tag": OUTCOME_TAG,
                "options": MCQ_OPTIONS,
                "answer_key": MCQ_CORRECT,
            },
        ).json()
        client.post(f"/api/challenges/{challenge['id']}/publish")

        _sign_in_as(client, "student", STUDENT)
        client.post("/enrollment")
        client.post(
            f"/api/assessments/items/{item['id']}/responses",
            json={"answer": "Once, when I turn 18"},
        )

        _sign_in_as(client, "staff", ADMIN)
        setup = {
            "challenge_id": challenge["id"],
            "task_id": task["id"],
            "item_id": item["id"],
        }
        row = client.get(_responses_url(setup)).json()[0]
        assert row["score"] == 0.0
        assert row["ai_feedback"] is None, "MCQ feedback is never stored"

        body = client.patch(
            f"{_responses_url(setup)}/{row['id']}", json={"score": 1.0}
        ).json()
        assert body["score"] == 1.0
        assert body["scored_by"] == "human"


# ---------------------------------------------------------------------------
# Score bounds
# ---------------------------------------------------------------------------


class TestScoreBounds:
    @pytest.mark.parametrize("score", [1.4, -0.1, 5])
    def test_a_score_outside_the_range_is_422(self, client, scored, score):
        """An admin who types 5 meant 0.5 or slipped; either way a 422 naming the range
        is more use than a silently clamped 1.0 skewing the FR-F4 mean."""
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": score}
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("score", [0.0, 1.0])
    def test_the_boundaries_are_accepted(self, client, scored, score):
        """0.0 and 1.0 are legitimate scores, not off-by-one casualties."""
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": score}
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == score

    def test_a_rejected_score_changes_nothing(self, client, scored):
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 9.0}
        )
        assert resp.status_code == 422

        row = client.get(_responses_url(scored)).json()[0]
        assert row["score"] == scored["result"]["score"]
        assert row["scored_by"] == "auto"


# ---------------------------------------------------------------------------
# The listing surface
# ---------------------------------------------------------------------------


class TestListing:
    def test_it_surfaces_only_the_student_id_and_subject(self, client, scored):
        """The no-PHI posture. Student carries no name and no campus ID number, and this
        surface adds nothing to what exists — the schema is the guarantee.
        """
        row = client.get(_responses_url(scored)).json()[0]
        assert set(row) == {
            "id",
            "student_id",
            "student_subject",
            "response",
            "score",
            "scored_by",
            "ai_feedback",
            "ts",
        }
        assert row["student_subject"] == STUDENT

    def test_an_admin_can_reach_responses_on_a_superseded_challenge(self, client, scored):
        """The whole reason these routes do not reuse the student-side item lookup.

        That helper resolves the campus's *active* challenge — the most recently starting
        published one — which is right for a student and wrong for an admin. Publishing
        next semester's challenge silently strands last semester's: the responses still
        exist, an admin still has to be able to read and fix them, and going through the
        student's lookup would 404 every one of them the moment the new term opens.
        """
        newer = client.post(
            "/api/challenges",
            json={
                "name": "Spring 2026 Wellness",
                "semester": "Spring 2026",
                "start_date": "2026-01-15",  # starts later, so it wins "active"
                "end_date": "2026-05-15",
            },
        ).json()
        assert client.post(f"/api/challenges/{newer['id']}/publish").status_code == 200

        listed = client.get(_responses_url(scored))
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        patched = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.5}
        )
        assert patched.status_code == 200
        assert patched.json()["scored_by"] == "human"

    def test_an_admin_can_reach_responses_on_a_draft_challenge(
        self, client, db_sessionmaker, scored
    ):
        """The same guarantee for a challenge that was never published.

        Unreachable through the API today — there is no unpublish route, and a draft
        cannot collect responses — so the state is built directly. It is tested anyway
        because the admin lookup deliberately does not filter on status, and that is the
        property worth pinning rather than the route that happens to exist this week.
        """
        with db_sessionmaker() as db:
            challenge = db.get(Challenge, scored["challenge_id"])
            challenge.status = "draft"
            db.commit()

        assert client.get(_responses_url(scored)).status_code == 200
        assert (
            client.patch(
                f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 0.5}
            ).status_code
            == 200
        )

    def test_an_item_with_no_responses_lists_empty(self, client, scored):
        """Empty is not an error — most items have no answers yet."""
        _sign_in_as(client, "staff", ADMIN)
        other = client.post(
            f"/api/challenges/{scored['challenge_id']}/tasks/{scored['task_id']}/items",
            json={
                "item_type": "reflection",
                "prompt": "Another prompt",
                "outcome_tag": OUTCOME_TAG,
                "rubric": RUBRIC,
            },
        ).json()

        resp = client.get(_responses_url({**scored, "item_id": other["id"]}))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


class TestAccess:
    def test_a_student_cannot_override(self, client, scored):
        _sign_in_as(client, "student", STUDENT)
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 1.0}
        )
        assert resp.status_code == 403

    def test_a_student_cannot_read_the_responses(self, client, scored):
        """Otherwise the listing is a way to read other students' reflections."""
        _sign_in_as(client, "student", STUDENT)
        assert client.get(_responses_url(scored)).status_code == 403

    def test_an_unauthenticated_override_is_401(self, client, scored):
        client.cookies.clear()
        resp = client.patch(
            f"{_responses_url(scored)}/{scored['response_id']}", json={"score": 1.0}
        )
        assert resp.status_code == 401

    def test_a_response_on_a_different_item_is_404(self, client, scored):
        """The item_id filter is what stops an override landing on the wrong question."""
        other = client.post(
            f"/api/challenges/{scored['challenge_id']}/tasks/{scored['task_id']}/items",
            json={
                "item_type": "reflection",
                "prompt": "Another prompt",
                "outcome_tag": OUTCOME_TAG,
                "rubric": RUBRIC,
            },
        ).json()

        other_url = _responses_url({**scored, "item_id": other["id"]})
        resp = client.patch(f"{other_url}/{scored['response_id']}", json={"score": 1.0})
        assert resp.status_code == 404

    def test_an_unknown_response_is_404(self, client, scored):
        resp = client.patch(f"{_responses_url(scored)}/999999", json={"score": 1.0})
        assert resp.status_code == 404

    def test_an_admin_from_another_campus_gets_404(self, client, db_sessionmaker):
        """Campus isolation comes from the challenge chain, not from a check on the row.

        The mock IdP always resolves to campus_id="csub", so the rival campus's data can
        only be created directly.
        """
        with db_sessionmaker() as db:
            rival = Challenge(
                campus_id="other",
                name="Rival Challenge",
                semester="Fall 2025",
                start_date=date(2025, 9, 1),
                end_date=date(2025, 12, 15),
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
            rival_ids = {
                "challenge_id": rival.id,
                "task_id": rival_task.id,
                "item_id": rival_item.id,
            }

        _sign_in_as(client, "staff", ADMIN)
        assert client.get(_responses_url(rival_ids)).status_code == 404
