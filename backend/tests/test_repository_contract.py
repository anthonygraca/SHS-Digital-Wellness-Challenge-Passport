"""Contract tests: the Repository protocol must behave identically on both backends.

Every test here runs twice — against ``SqlAlchemyRepository`` (in-memory SQLite) and
``DynamoRepository`` (moto, tables built from ``template.yaml``). This is the guard the
Dynamo port relies on: production runs Dynamo, but until this suite existed only the SQL
path was exercised (the route tests bind SQL). Each later PR that adds a method to the
``Repository`` protocol extends this suite in the same commit.

With ``WP_DDB_ENDPOINT_URL`` set, the dynamo parameter runs against DynamoDB Local
instead of moto (see tests/ddb_support.py) — the same assertions, AWS's own engine.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.repositories.sqlalchemy_repo import SqlAlchemyRepository
from app.schemas.challenge import (
    ChallengeCreate,
    MCQCreate,
    TaskCreate,
    TaskReorder,
)
from app.services.passport import DuplicateCheckIn, InvalidEventToken
from app.services.qr import mint_event_token
from tests.ddb_support import dynamo_backend, set_env


@pytest.fixture(params=["sql", "dynamo"])
def repo(request, monkeypatch):
    if request.param == "sql":
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        # expire_on_commit=True so a read after a write re-queries rather than serving a
        # cached ORM relationship. Production gets this for free — a fresh session per
        # request — but the contract reuses one session across operations, and without
        # this the SQL path would report stale post-delete tasks while Dynamo (fresh
        # DTOs each call) reports the truth. The contract is about observable behavior on
        # independent reads, which is what expiring gives us.
        db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)()
        try:
            yield SqlAlchemyRepository(db)
        finally:
            db.close()
            engine.dispose()
    else:
        from app.config import get_settings
        from app.repositories.dynamo_repo import DynamoRepository, reset_tables

        set_env(monkeypatch)
        get_settings.cache_clear()
        with dynamo_backend():
            reset_tables()
            yield DynamoRepository()
        reset_tables()
        get_settings.cache_clear()


# --- helpers ----------------------------------------------------------------
def _challenge(repo, name="Fall", semester="Fall 2026", publish=True):
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


def _built_challenge(repo, titles=("Week 1", "Week 2")):
    """A published challenge with tasks — built draft-first, the real order."""
    ch = _challenge(repo, publish=False)
    tasks = [repo.add_task(ch.id, TaskCreate(title=t)) for t in titles]
    repo.publish_challenge("csub", ch.id)
    return ch, tasks


def _student(repo, sso="stu@csub.edu"):
    return repo.get_or_create_student("csub", sso, "student")


# --- challenges -------------------------------------------------------------
def test_ids_increment_from_one(repo):
    a = _challenge(repo, name="A", publish=False)
    b = _challenge(repo, name="B", publish=False)
    assert (a.id, b.id) == (1, 2)


def test_only_published_is_active_and_latest_start_wins(repo):
    assert repo.get_active_challenge("csub") is None
    _challenge(repo, name="Draft", publish=False)
    assert repo.get_active_challenge("csub") is None  # a draft is not active

    early = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name="Early", semester="S1", start_date="2026-01-01", end_date="2026-02-01"
        ),
    )
    repo.publish_challenge("csub", early.id)
    late = _challenge(repo, name="Late")  # starts 2026-09-01
    active = repo.get_active_challenge("csub")
    assert active is not None and active.id == late.id


def test_active_challenge_is_campus_scoped(repo):
    _challenge(repo)
    assert repo.get_active_challenge("other-campus") is None


# --- tasks ------------------------------------------------------------------
def test_task_positions_reorder_and_delete_closes_the_gap(repo):
    ch = _challenge(repo, publish=False)
    t1 = repo.add_task(ch.id, TaskCreate(title="W1"))
    t2 = repo.add_task(ch.id, TaskCreate(title="W2"))
    t3 = repo.add_task(ch.id, TaskCreate(title="W3"))
    assert [t1.position, t2.position, t3.position] == [1, 2, 3]

    repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t3.id, t1.id, t2.id]))
    full = repo.get_challenge("csub", ch.id)
    assert [(t.id, t.position) for t in full.tasks] == [
        (t3.id, 1),
        (t1.id, 2),
        (t2.id, 3),
    ]

    repo.delete_task(ch.id, t1.id)  # was position 2
    full = repo.get_challenge("csub", ch.id)
    assert [t.position for t in full.tasks] == [1, 2]  # gap closed
    assert t1.id not in {t.id for t in full.tasks}


def test_reorder_rejects_a_wrong_id_set(repo):
    ch = _challenge(repo, publish=False)
    t1 = repo.add_task(ch.id, TaskCreate(title="W1"))
    with pytest.raises(ValueError):
        repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t1.id, 999]))


# --- assessment items -------------------------------------------------------
def test_assessment_item_crud(repo):
    ch = _challenge(repo, publish=False)
    t = repo.add_task(ch.id, TaskCreate(title="W1"))
    item = repo.add_item(
        t.id,
        MCQCreate(
            item_type="mcq",
            prompt="Q?",
            outcome_tag="vision-care",
            options=["a", "b"],
            answer_key="a",
        ),
    )
    assert repo.get_item(t.id, item.id) is not None
    assert [i.id for i in repo.list_items(t.id)] == [item.id]

    repo.delete_item(t.id, item.id)
    assert repo.get_item(t.id, item.id) is None
    assert repo.list_items(t.id) == []


# --- enrollment + students --------------------------------------------------
def test_enrollment_is_idempotent(repo):
    ch = _challenge(repo)
    stu = _student(repo)
    first = repo.enroll(stu.id, ch.id)
    second = repo.enroll(stu.id, ch.id)
    assert first.id == second.id
    assert repo.get_enrollment(stu.id, ch.id) is not None


def test_get_or_create_student_is_idempotent(repo):
    a = repo.get_or_create_student("csub", "sam@csub.edu", "student")
    b = repo.get_or_create_student("csub", "sam@csub.edu", "student")
    assert a.id == b.id


# --- passport (derived reads) + check-in writes -----------------------------
def test_passport_sequential_unlock_and_prize_eligibility(repo):
    ch, (t1, t2) = _built_challenge(repo)
    stu = _student(repo)

    view = repo.build_passport("csub", stu.id)
    assert [w.status for w in view.weeks] == ["available", "locked"]
    assert view.prize_eligible is False

    task, view = repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t1.id))
    assert task.position == 1
    # The returned passport reflects the check-in without a second challenge lookup.
    assert [w.status for w in view.weeks] == ["complete", "available"]
    assert view.completed_weeks == 1
    assert view.prize_eligible is False

    _, view = repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t2.id))
    assert view.prize_eligible is True  # every required task complete


def test_checkin_is_idempotent_and_tokens_are_validated(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    token = mint_event_token(t1.id)

    repo.record_event_qr_checkin("csub", stu.id, token)
    with pytest.raises(DuplicateCheckIn):
        repo.record_event_qr_checkin("csub", stu.id, token)
    with pytest.raises(InvalidEventToken):
        repo.record_event_qr_checkin("csub", stu.id, "not-a-real-token")


def test_completed_tasks_are_scoped_to_the_student(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")

    repo.record_event_qr_checkin("csub", alice.id, mint_event_token(t1.id))

    # Alice's check-in must not bleed into Bob's passport.
    bob_view = repo.build_passport("csub", bob.id)
    assert [w.status for w in bob_view.weeks] == ["available"]
    alice_view = repo.build_passport("csub", alice.id)
    assert [w.status for w in alice_view.weeks] == ["complete"]
