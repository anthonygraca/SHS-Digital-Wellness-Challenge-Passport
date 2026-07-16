"""Verify the DynamoDB repository against a moto-mocked DynamoDB.

Exercises the invariants that DynamoDB does not enforce for us and that the SQL
path got for free: integer-id counters, (campus,name,semester) seed idempotency,
per-position task ordering + gap-closing delete, enrollment/student/check-in
idempotency via conditional writes, and the derived passport (sequential unlock +
prize eligibility). Tables are created with the same key schema + GSIs the SAM
template provisions, so this doubles as a schema contract check.
"""

from __future__ import annotations

import pytest

from app.schemas.challenge import (
    ChallengeCreate,
    MCQCreate,
    TaskCreate,
    TaskReorder,
    TaskUpdate,
)
from app.services.qr import mint_event_token
from tests.ddb_support import dynamo_backend, set_env


@pytest.fixture
def repo(monkeypatch):
    from app.config import get_settings
    from app.repositories.dynamo_repo import DynamoRepository, reset_tables

    set_env(monkeypatch)
    get_settings.cache_clear()
    with dynamo_backend():
        # Rebuild the module-cached table handles against this test's fresh backend.
        reset_tables()
        yield DynamoRepository()
    reset_tables()
    get_settings.cache_clear()


def _mk_challenge(repo, name="Fall Challenge", semester="Fall 2026", publish=True):
    ch = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name=name,
            semester=semester,
            start_date="2026-09-01",
            end_date="2026-12-01",
        ),
    )
    if publish:
        repo.publish_challenge("csub", ch.id)
    return ch


def _add_task(repo, cid, title, required=True):
    return repo.add_task(cid, TaskCreate(title=title, required=required))


def test_counters_yield_incrementing_ids(repo):
    a = _mk_challenge(repo, name="A", publish=False)
    b = _mk_challenge(repo, name="B", publish=False)
    assert a.id == 1
    assert b.id == 2


def test_create_publish_and_active_challenge(repo):
    ch = _mk_challenge(repo)
    active = repo.get_active_challenge("csub")
    assert active is not None
    assert active.id == ch.id
    assert active.name == "Fall Challenge"
    # Draft challenges are not active.
    assert repo.get_active_challenge("other-campus") is None


def test_latest_published_wins(repo):
    old = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name="Old", semester="S1", start_date="2026-01-01", end_date="2026-02-01"
        ),
    )
    repo.publish_challenge("csub", old.id)
    new = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name="New", semester="S2", start_date="2026-09-01", end_date="2026-10-01"
        ),
    )
    repo.publish_challenge("csub", new.id)
    active = repo.get_active_challenge("csub")
    assert active.id == new.id  # later start_date wins


def test_seed_identity_lookup(repo):
    _mk_challenge(repo, name="Stranger Things", semester="Fall 2026", publish=False)
    found = repo.find_challenge_by_identity("csub", "Stranger Things", "Fall 2026")
    assert found is not None
    assert repo.find_challenge_by_identity("csub", "Stranger Things", "Spring") is None


def test_tasks_ordered_and_get_challenge_nested(repo):
    ch = _mk_challenge(repo, publish=False)
    t1 = _add_task(repo, ch.id, "Week 1")
    t2 = _add_task(repo, ch.id, "Week 2")
    assert (t1.position, t2.position) == (1, 2)
    repo.add_item(
        t1.id,
        MCQCreate(
            item_type="mcq",
            prompt="Q?",
            outcome_tag="tag",
            options=["A", "B"],
            answer_key="A",
        ),
    )
    full = repo.get_challenge("csub", ch.id)
    assert [t.position for t in full.tasks] == [1, 2]
    assert full.tasks[0].assessment_items[0].prompt == "Q?"
    assert full.tasks[1].assessment_items == []


def test_delete_task_cascades_items_and_closes_gap(repo):
    ch = _mk_challenge(repo, publish=False)
    t1 = _add_task(repo, ch.id, "Week 1")
    t2 = _add_task(repo, ch.id, "Week 2")
    t3 = _add_task(repo, ch.id, "Week 3")
    repo.add_item(
        t2.id,
        MCQCreate(
            item_type="mcq",
            prompt="Q",
            outcome_tag="t",
            options=["A", "B"],
            answer_key="A",
        ),
    )
    repo.delete_task(ch.id, t2.id)
    remaining = repo.get_challenge("csub", ch.id).tasks
    assert [(t.id, t.position) for t in remaining] == [(t1.id, 1), (t3.id, 2)]
    # The deleted task's items are gone.
    assert repo.list_items(t2.id) == []


def test_reorder_tasks(repo):
    ch = _mk_challenge(repo, publish=False)
    t1 = _add_task(repo, ch.id, "Week 1")
    t2 = _add_task(repo, ch.id, "Week 2")
    t3 = _add_task(repo, ch.id, "Week 3")
    out = repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t3.id, t1.id, t2.id]))
    assert [t.id for t in out] == [t3.id, t1.id, t2.id]
    assert [t.position for t in out] == [1, 2, 3]


def test_reorder_wrong_ids_rejected(repo):
    ch = _mk_challenge(repo, publish=False)
    t1 = _add_task(repo, ch.id, "Week 1")
    with pytest.raises(ValueError):
        repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t1.id, 999]))


def test_update_task(repo):
    ch = _mk_challenge(repo, publish=False)
    t = _add_task(repo, ch.id, "Week 1")
    updated = repo.update_task(ch.id, t.id, TaskUpdate(title="Renamed"))
    assert updated.title == "Renamed"
    assert updated.position == 1


def test_student_and_enrollment_idempotent(repo):
    s1 = repo.get_or_create_student("csub", "abc@csub.edu", "student")
    s2 = repo.get_or_create_student("csub", "abc@csub.edu", "student")
    assert s1.id == s2.id == "csub#abc@csub.edu"
    ch = _mk_challenge(repo)
    e1 = repo.enroll(s1.id, ch.id)
    e2 = repo.enroll(s1.id, ch.id)
    assert e1.challenge_id == e2.challenge_id == ch.id
    assert repo.get_enrollment(s1.id, ch.id) is not None


def test_checkin_drives_passport_status(repo):
    ch = _mk_challenge(repo)
    t1 = _add_task(repo, ch.id, "Week 1", required=True)
    t2 = _add_task(repo, ch.id, "Week 2", required=True)
    student_id = "csub#stu@csub.edu"

    view = repo.build_passport("csub", student_id)
    assert [w.status for w in view.weeks] == ["available", "locked"]
    assert view.prize_eligible is False

    repo.record_event_qr_checkin("csub", student_id, mint_event_token(t1.id))
    view = repo.build_passport("csub", student_id)
    assert [w.status for w in view.weeks] == ["complete", "available"]
    assert view.completed_weeks == 1
    assert view.prize_eligible is False

    repo.record_event_qr_checkin("csub", student_id, mint_event_token(t2.id))
    view = repo.build_passport("csub", student_id)
    assert view.prize_eligible is True  # all required tasks complete


def test_event_qr_checkin(repo):
    ch = _mk_challenge(repo)
    t = _add_task(repo, ch.id, "Week 1")
    student_id = "csub#qr@csub.edu"
    token = mint_event_token(t.id)

    task, view = repo.record_event_qr_checkin("csub", student_id, token)
    assert task.position == 1
    # The refreshed passport is returned alongside the task (no second challenge lookup).
    assert [w.status for w in view.weeks] == ["complete"]

    # Duplicate scan of the same week -> DuplicateCheckIn.
    from app.services.passport import DuplicateCheckIn, InvalidEventToken

    with pytest.raises(DuplicateCheckIn):
        repo.record_event_qr_checkin("csub", student_id, token)

    # Tampered / unknown token -> InvalidEventToken.
    with pytest.raises(InvalidEventToken):
        repo.record_event_qr_checkin("csub", student_id, "not-a-token")
