"""DynamoDB-backed repository (persistence="dynamo", used on AWS Lambda).

Multi-table model — one table per entity, mirroring the SQLite schema:

    {prefix}Students          PK student_id (S = "<campus>#<sso>")
    {prefix}Challenges        PK id (N)
                              GSI ByCampus          (campus_id, created_at)
                              GSI PublishedByCampus (pub_campus_id, published_sort)
    {prefix}Tasks             PK id (N)
                              GSI ByChallenge      (challenge_id, position)
    {prefix}AssessmentItems   PK id (N)
                              GSI ByTask           (task_id)
                              GSI ByChallenge      (challenge_id)
    {prefix}Enrollments       PK student_id (S), SK challenge_id (N)
    {prefix}CheckIns          PK student_id (S), SK task_id (N)
                              GSI ByTask           (task_id, ts)
                              GSI ByChallenge      (challenge_id, ts)
    {prefix}CheckInAudits     PK task_id (N), SK audit_id (S = "<ts>#<id>")
    {prefix}Themes            PK id (S = the theme slug)
    {prefix}Counters          PK name (S), attr seq (N)   [integer-id allocation]

The base CheckIns key answers the student's question ("have I done this task?"); the
two GSIs answer the admin's ("who has done this task / this challenge?"), which the
base key cannot. ``challenge_id`` is denormalized onto the row for the second one.

DynamoDB has no constraints, so the SQL invariants are re-implemented here:
uniqueness/idempotency via conditional writes, cascade-delete + position renumber in
code, and integer ids via an atomic counter. FR-D6's "a completion never changes
without leaving a trace" spans two tables, so it needs TransactWriteItems rather than
a commit. The pure passport derivation and the QR token + exceptions are shared with
the SQL path (app.services.passport / .qr), as is the audit snapshot shape
(app.services.checkins.checkin_snapshot).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.config import get_settings
from app.repositories.dto import (
    AssessmentItemDTO,
    AssessmentResponseDTO,
    ChallengeDTO,
    CheckInAuditDTO,
    CheckInDTO,
    EnrollmentDTO,
    StudentDTO,
    TaskDTO,
    ThemeDTO,
)
from app.schemas.challenge import (
    AssessmentItemUpdate,
    ChallengeCreate,
    ChallengeUpdate,
    MCQCreate,
    ReflectionCreate,
    TaskCreate,
    TaskReorder,
    TaskUpdate,
)
from app.schemas.theme import ThemeCreate, ThemeUpdate
from app.services.checkins import checkin_snapshot
from app.services.passport import (
    DuplicateCheckIn,
    InvalidEventToken,
    PassportView,
    ThemeConfigView,
    assemble_passport,
)
from app.services.qr import verify_event_token


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enc(value: Any) -> Any:
    """Encode a Python value for a DynamoDB attribute.

    datetimes/dates -> ISO strings; floats -> Decimal, because boto3 refuses a Python
    float outright ("Float types are not supported. Use Decimal types instead"), and
    AssessmentResponse.score is one. ``Decimal(str(x))`` rather than ``Decimal(x)``:
    the latter carries the binary float's noise (0.1 -> 0.1000000000000000055...) into
    the stored value, so a score would come back subtly different from the one scored.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    # bool is an int subclass, not a float, so it is unaffected by this branch.
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _prune(item: dict) -> dict:
    """Drop None values — DynamoDB attributes are simply absent rather than NULL."""
    return {k: v for k, v in item.items() if v is not None}


def _int(value: Any) -> int:
    return int(value) if isinstance(value, Decimal) else int(value)


def _float(value: Any) -> float | None:
    """Read a number back as a float — DynamoDB hands every number back as Decimal."""
    return float(value) if value is not None else None


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _dt(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


# Repo-attribute name -> table-name suffix (SAM names tables `{prefix}{Suffix}`).
_TABLE_SUFFIXES = {
    "students": "Students",
    "challenges": "Challenges",
    "tasks": "Tasks",
    "items": "AssessmentItems",
    "enrollments": "Enrollments",
    "checkins": "CheckIns",
    "audits": "CheckInAudits",
    "responses": "AssessmentResponses",
    "views": "ContentViews",
    "counters": "Counters",
    "themes": "Themes",
}

_tables_cache: dict[str, Any] | None = None


def _tables() -> dict[str, Any]:
    """Build (once) and return the boto3 Table handles, keyed by repo attribute name.

    Cached at module scope: ``boto3.resource()`` parses the botocore service model
    (tens of ms) and ``get_repo`` constructs a ``DynamoRepository`` per request, so
    building the resource per request added that cost to every API call. On Lambda the
    cache persists across warm invocations. Tests call :func:`reset_tables` after
    entering a fresh moto / DynamoDB-Local context so the handles rebuild against it.
    """
    global _tables_cache
    if _tables_cache is None:
        settings = get_settings()
        kwargs: dict[str, Any] = {}
        if settings.aws_region:
            kwargs["region_name"] = settings.aws_region
        if settings.ddb_endpoint_url:
            kwargs["endpoint_url"] = settings.ddb_endpoint_url
        ddb = boto3.resource("dynamodb", **kwargs)
        p = settings.ddb_table_prefix
        _tables_cache = {
            attr: ddb.Table(f"{p}{suffix}") for attr, suffix in _TABLE_SUFFIXES.items()
        }
    return _tables_cache


def reset_tables() -> None:
    """Drop the cached Table handles so the next use rebuilds them.

    Only tests need this: they swap the moto / DynamoDB-Local backend between cases,
    and a handle cached against a torn-down backend would find no tables.
    """
    global _tables_cache
    _tables_cache = None


class DynamoRepository:
    def __init__(self) -> None:
        t = _tables()
        self.students = t["students"]
        self.challenges = t["challenges"]
        self.tasks = t["tasks"]
        self.items = t["items"]
        self.enrollments = t["enrollments"]
        self.checkins = t["checkins"]
        self.audits = t["audits"]
        self.responses = t["responses"]
        self.views = t["views"]
        self.counters = t["counters"]
        self.themes = t["themes"]

    # --- helpers ------------------------------------------------------------
    def _next_id(self, name: str) -> int:
        resp = self.counters.update_item(
            Key={"name": name},
            UpdateExpression="ADD seq :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return _int(resp["Attributes"]["seq"])

    @staticmethod
    def _query_all(table, **kwargs) -> list[dict]:
        items: list[dict] = []
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = table.query(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
            items.extend(resp.get("Items", []))
        return items

    # --- DTO mappers --------------------------------------------------------
    @staticmethod
    def _item_dto(raw: dict) -> AssessmentItemDTO:
        return AssessmentItemDTO(
            id=_int(raw["id"]),
            task_id=_int(raw["task_id"]),
            item_type=raw["item_type"],
            prompt=raw["prompt"],
            outcome_tag=raw["outcome_tag"],
            options=raw.get("options"),
            answer_key=raw.get("answer_key"),
            rubric=raw.get("rubric"),
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
        )

    def _task_dto(self, raw: dict, *, with_items: bool = False) -> TaskDTO:
        items: list[AssessmentItemDTO] = []
        if with_items:
            rows = self._query_all(
                self.items,
                IndexName="ByTask",
                KeyConditionExpression=Key("task_id").eq(_int(raw["id"])),
            )
            items = [self._item_dto(r) for r in rows]
        return TaskDTO(
            id=_int(raw["id"]),
            challenge_id=_int(raw["challenge_id"]),
            position=_int(raw["position"]),
            title=raw["title"],
            caption=raw.get("caption", ""),
            activity_type=raw.get("activity_type", ""),
            location=raw.get("location", ""),
            date_window_start=_date(raw.get("date_window_start")),
            date_window_end=_date(raw.get("date_window_end")),
            prize=raw.get("prize", ""),
            required=bool(raw.get("required", True)),
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            assessment_items=items,
        )

    def _challenge_dto(self, raw: dict, *, with_tasks: bool = False) -> ChallengeDTO:
        tasks: list[TaskDTO] = []
        if with_tasks:
            tasks = self._tasks_for_challenge(_int(raw["id"]), with_items=True)
        return ChallengeDTO(
            id=_int(raw["id"]),
            campus_id=raw["campus_id"],
            name=raw["name"],
            semester=raw["semester"],
            start_date=_date(raw.get("start_date")),
            end_date=_date(raw.get("end_date")),
            status=raw.get("status", "draft"),
            theme_id=raw.get("theme_id", ""),
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            tasks=tasks,
        )

    def _tasks_for_challenge(
        self, challenge_id: int, *, with_items: bool = False
    ) -> list[TaskDTO]:
        rows = self._query_all(
            self.tasks,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id),
        )
        rows.sort(key=lambda r: _int(r["position"]))
        if not with_items:
            return [self._task_dto(r) for r in rows]
        # One batched query for the whole challenge's items, grouped by task — avoids
        # a per-task round trip (the single-table design's N+1 win, kept here).
        item_rows = self._query_all(
            self.items,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id),
        )
        by_task: dict[int, list[AssessmentItemDTO]] = {}
        for ir in item_rows:
            by_task.setdefault(_int(ir["task_id"]), []).append(self._item_dto(ir))
        out: list[TaskDTO] = []
        for r in rows:
            dto = self._task_dto(r)
            dto.assessment_items = by_task.get(dto.id, [])
            out.append(dto)
        return out

    # --- Challenges ---------------------------------------------------------
    def create_challenge(self, campus_id: str, data: ChallengeCreate) -> ChallengeDTO:
        now = _now()
        cid = self._next_id("challenge")
        item = _prune(
            {
                "id": cid,
                "campus_id": campus_id,
                "name": data.name,
                "semester": data.semester,
                "start_date": _enc(data.start_date),
                "end_date": _enc(data.end_date),
                "theme_id": "",
                "status": "draft",
                "created_at": _enc(now),
                "updated_at": _enc(now),
            }
        )
        self.challenges.put_item(Item=item)
        return self._challenge_dto(item, with_tasks=True)

    def list_challenges(self, campus_id: str) -> list[ChallengeDTO]:
        rows = self._query_all(
            self.challenges,
            IndexName="ByCampus",
            KeyConditionExpression=Key("campus_id").eq(campus_id),
            ScanIndexForward=False,  # created_at DESC
        )
        return [self._challenge_dto(r) for r in rows]

    def _raw_challenge(self, campus_id: str, challenge_id: int) -> dict | None:
        raw = self.challenges.get_item(Key={"id": challenge_id}).get("Item")
        if raw is None or raw.get("campus_id") != campus_id:
            return None
        return raw

    def get_challenge(self, campus_id: str, challenge_id: int) -> ChallengeDTO | None:
        raw = self._raw_challenge(campus_id, challenge_id)
        return self._challenge_dto(raw, with_tasks=True) if raw else None

    def update_challenge(
        self, campus_id: str, challenge_id: int, data: ChallengeUpdate
    ) -> ChallengeDTO | None:
        raw = self._raw_challenge(campus_id, challenge_id)
        if raw is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            raw[field] = _enc(value)
        raw["updated_at"] = _enc(_now())
        if raw.get("status") == "published":
            raw["pub_campus_id"] = raw["campus_id"]
            raw["published_sort"] = f"{raw['start_date']}#{raw['created_at']}"
        self.challenges.put_item(Item=_prune(raw))
        return self._challenge_dto(raw, with_tasks=True)

    def publish_challenge(self, campus_id: str, challenge_id: int) -> ChallengeDTO | None:
        raw = self._raw_challenge(campus_id, challenge_id)
        if raw is None:
            return None
        raw["status"] = "published"
        raw["updated_at"] = _enc(_now())
        raw["pub_campus_id"] = raw["campus_id"]
        raw["published_sort"] = f"{raw['start_date']}#{raw['created_at']}"
        self.challenges.put_item(Item=_prune(raw))
        return self._challenge_dto(raw, with_tasks=True)

    def get_active_challenge(self, campus_id: str) -> ChallengeDTO | None:
        # Only the latest-starting published challenge matters, so read exactly one
        # row (Limit=1) rather than paginating the whole partition to discard all but
        # rows[0] — this is on the passport hot path.
        resp = self.challenges.query(
            IndexName="PublishedByCampus",
            KeyConditionExpression=Key("pub_campus_id").eq(campus_id),
            ScanIndexForward=False,  # published_sort DESC -> latest start_date wins
            Limit=1,
        )
        rows = resp.get("Items", [])
        if not rows:
            return None
        return self._challenge_dto(rows[0])

    def find_challenge_by_identity(
        self, campus_id: str, name: str, semester: str
    ) -> ChallengeDTO | None:
        """Seed idempotency key — the Dynamo analogue of uq_challenge_campus_name_sem."""
        rows = self._query_all(
            self.challenges,
            IndexName="ByCampus",
            KeyConditionExpression=Key("campus_id").eq(campus_id),
        )
        for r in rows:
            if r.get("name") == name and r.get("semester") == semester:
                return self._challenge_dto(r)
        return None

    # --- Tasks --------------------------------------------------------------
    def add_task(self, challenge_id: int, data: TaskCreate) -> TaskDTO:
        existing = self._query_all(
            self.tasks,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id),
        )
        position = len(existing) + 1
        now = _now()
        tid = self._next_id("task")
        item = _prune(
            {
                "id": tid,
                "challenge_id": challenge_id,
                "position": position,
                "title": data.title,
                "caption": data.caption,
                "activity_type": data.activity_type,
                "location": data.location,
                "date_window_start": _enc(data.date_window_start),
                "date_window_end": _enc(data.date_window_end),
                "prize": data.prize,
                "required": data.required,
                "created_at": _enc(now),
                "updated_at": _enc(now),
            }
        )
        self.tasks.put_item(Item=item)
        return self._task_dto(item)

    def _raw_task(self, challenge_id: int, task_id: int) -> dict | None:
        raw = self.tasks.get_item(Key={"id": task_id}).get("Item")
        if raw is None or _int(raw.get("challenge_id")) != challenge_id:
            return None
        return raw

    def get_task(self, challenge_id: int, task_id: int) -> TaskDTO | None:
        raw = self._raw_task(challenge_id, task_id)
        return self._task_dto(raw, with_items=True) if raw else None

    def update_task(
        self, challenge_id: int, task_id: int, data: TaskUpdate
    ) -> TaskDTO | None:
        raw = self._raw_task(challenge_id, task_id)
        if raw is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            raw[field] = _enc(value)
        raw["updated_at"] = _enc(_now())
        self.tasks.put_item(Item=_prune(raw))
        return self._task_dto(raw, with_items=True)

    def delete_task(self, challenge_id: int, task_id: int) -> None:
        raw = self._raw_task(challenge_id, task_id)
        if raw is None:
            return
        position = _int(raw["position"])
        self.tasks.delete_item(Key={"id": task_id})
        # Cascade: delete the task's assessment items.
        item_rows = self._query_all(
            self.items,
            IndexName="ByTask",
            KeyConditionExpression=Key("task_id").eq(task_id),
        )
        with self.items.batch_writer() as batch:
            for ir in item_rows:
                batch.delete_item(Key={"id": _int(ir["id"])})
        # Close the position gap: decrement every task after the removed one. A serial
        # update loop, not a batch — this is an admin edit over a challenge's ~6 tasks,
        # and update_item cannot go in a batch_writer (put/delete only). Not worth the
        # complexity of a transaction at this scale.
        remaining = self._query_all(
            self.tasks,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id),
        )
        for t in remaining:
            if _int(t["position"]) > position:
                self.tasks.update_item(
                    Key={"id": _int(t["id"])},
                    UpdateExpression="SET #p = #p - :one",
                    ExpressionAttributeNames={"#p": "position"},
                    ExpressionAttributeValues={":one": 1},
                )

    def reorder_tasks(self, challenge_id: int, data: TaskReorder) -> list[TaskDTO]:
        existing = self._query_all(
            self.tasks,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id),
        )
        existing_ids = {_int(t["id"]) for t in existing}
        incoming_ids = set(data.task_ids)
        if existing_ids != incoming_ids:
            raise ValueError(
                "task_ids must contain exactly the IDs of all tasks in this challenge"
            )
        for new_position, task_id in enumerate(data.task_ids, start=1):
            self.tasks.update_item(
                Key={"id": task_id},
                UpdateExpression="SET #p = :pos",
                ExpressionAttributeNames={"#p": "position"},
                ExpressionAttributeValues={":pos": new_position},
            )
        return self._tasks_for_challenge(challenge_id, with_items=True)

    # --- Assessment items ---------------------------------------------------
    def add_item(
        self, task_id: int, data: MCQCreate | ReflectionCreate
    ) -> AssessmentItemDTO:
        task = self.tasks.get_item(Key={"id": task_id}).get("Item")
        challenge_id = _int(task["challenge_id"]) if task else 0
        now = _now()
        iid = self._next_id("item")
        item = _prune(
            {
                "id": iid,
                "task_id": task_id,
                "challenge_id": challenge_id,
                "item_type": data.item_type,
                "prompt": data.prompt,
                "outcome_tag": data.outcome_tag,
                "options": data.options if data.item_type == "mcq" else None,
                "answer_key": data.answer_key if data.item_type == "mcq" else None,
                "rubric": data.rubric if data.item_type == "reflection" else None,
                "created_at": _enc(now),
                "updated_at": _enc(now),
            }
        )
        self.items.put_item(Item=item)
        return self._item_dto(item)

    def list_items(self, task_id: int) -> list[AssessmentItemDTO]:
        rows = self._query_all(
            self.items,
            IndexName="ByTask",
            KeyConditionExpression=Key("task_id").eq(task_id),
        )
        return [self._item_dto(r) for r in rows]

    def _raw_item(self, task_id: int, item_id: int) -> dict | None:
        raw = self.items.get_item(Key={"id": item_id}).get("Item")
        if raw is None or _int(raw.get("task_id")) != task_id:
            return None
        return raw

    def get_item(self, task_id: int, item_id: int) -> AssessmentItemDTO | None:
        raw = self._raw_item(task_id, item_id)
        return self._item_dto(raw) if raw else None

    def update_item(
        self, task_id: int, item_id: int, data: AssessmentItemUpdate
    ) -> AssessmentItemDTO | None:
        raw = self._raw_item(task_id, item_id)
        if raw is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            raw[field] = _enc(value)
        raw["updated_at"] = _enc(_now())
        self.items.put_item(Item=_prune(raw))
        return self._item_dto(raw)

    def delete_item(self, task_id: int, item_id: int) -> None:
        raw = self._raw_item(task_id, item_id)
        if raw is not None:
            self.items.delete_item(Key={"id": item_id})

    # --- Enrollment ---------------------------------------------------------
    def get_enrollment(self, student_id, challenge_id: int) -> EnrollmentDTO | None:
        raw = self.enrollments.get_item(
            Key={"student_id": student_id, "challenge_id": challenge_id}
        ).get("Item")
        return self._enrollment_dto(raw) if raw else None

    @staticmethod
    def _enrollment_dto(raw: dict) -> EnrollmentDTO:
        return EnrollmentDTO(
            id=f"{raw['student_id']}#{_int(raw['challenge_id'])}",
            student_id=raw["student_id"],
            challenge_id=_int(raw["challenge_id"]),
            enrolled_at=_dt(raw.get("enrolled_at")),
        )

    def enroll(self, student_id, challenge_id: int) -> EnrollmentDTO:
        now = _now()
        item = {
            "student_id": student_id,
            "challenge_id": challenge_id,
            "enrolled_at": _enc(now),
        }
        try:
            self.enrollments.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(student_id)",
            )
            return self._enrollment_dto(item)
        except self.enrollments.meta.client.exceptions.ConditionalCheckFailedException:
            existing = self.get_enrollment(student_id, challenge_id)
            assert existing is not None
            return existing

    # --- Students -----------------------------------------------------------
    @staticmethod
    def _student_dto(raw: dict) -> StudentDTO:
        return StudentDTO(
            id=raw["student_id"],
            campus_id=raw["campus_id"],
            sso_subject=raw["sso_subject"],
            affiliation=raw["affiliation"],
            created_at=_dt(raw.get("created_at")),
        )

    def get_or_create_student(
        self, campus_id: str, sso_subject: str, affiliation: str
    ) -> StudentDTO:
        student_id = f"{campus_id}#{sso_subject}"
        now = _now()
        item = {
            "student_id": student_id,
            "campus_id": campus_id,
            "sso_subject": sso_subject,
            "affiliation": affiliation,
            "created_at": _enc(now),
        }
        try:
            self.students.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(student_id)",
            )
            raw = item
        except self.students.meta.client.exceptions.ConditionalCheckFailedException:
            raw = self.students.get_item(Key={"student_id": student_id}).get("Item")
        return self._student_dto(raw)

    def get_student(self, campus_id: str, sso_subject: str) -> StudentDTO | None:
        # The key IS (campus, subject) on this backend, so the lookup the SQL path
        # does with a two-column filter is a point read here.
        raw = self.students.get_item(
            Key={"student_id": f"{campus_id}#{sso_subject}"}
        ).get("Item")
        return self._student_dto(raw) if raw else None

    def get_student_by_id(self, campus_id: str, student_id) -> StudentDTO | None:
        raw = self.students.get_item(Key={"student_id": student_id}).get("Item")
        if raw is None or raw.get("campus_id") != campus_id:
            return None
        return self._student_dto(raw)

    # --- Assessments + engagement (FR-E4/E5, US-23) -------------------------
    @staticmethod
    def _response_dto(raw: dict) -> AssessmentResponseDTO:
        return AssessmentResponseDTO(
            id=_int(raw["id"]),
            student_id=raw["student_id"],
            assessment_item_id=_int(raw["assessment_item_id"]),
            response=raw["response"],
            score=_float(raw.get("score")),
            scored_by=raw["scored_by"],
            ai_feedback=raw.get("ai_feedback"),
            ts=_dt(raw.get("ts")),
        )

    def get_task_by_position(self, challenge_id: int, position: int) -> TaskDTO | None:
        rows = self._query_all(
            self.tasks,
            IndexName="ByChallenge",
            KeyConditionExpression=Key("challenge_id").eq(challenge_id)
            & Key("position").eq(position),
        )
        # .first(), like the SQL side: positions are kept gapless and unique by the
        # reorder service but no constraint enforces it, and a duplicate must not 500.
        return self._task_dto(rows[0]) if rows else None

    def get_item_in_challenge(self, challenge_id: int, item_id: int):
        raw = self.items.get_item(Key={"id": item_id}).get("Item")
        # challenge_id is denormalized onto the item, so scoping it to the challenge is
        # a comparison rather than the SQL path's join through Task.
        if raw is None or _int(raw.get("challenge_id", 0)) != challenge_id:
            return None
        return self._item_dto(raw)

    def get_response(self, student_id, item_id: int):
        raw = self.responses.get_item(
            Key={"student_id": student_id, "assessment_item_id": item_id}
        ).get("Item")
        return self._response_dto(raw) if raw else None

    def get_responses_for_items(self, student_id, item_ids: list[int]):
        if not item_ids:
            return {}
        found: dict[int, AssessmentResponseDTO] = {}
        # The keys are known — this week's items — so this is a BatchGetItem rather
        # than the SQL path's IN-clause query.
        keys = [{"student_id": student_id, "assessment_item_id": i} for i in item_ids]
        for start in range(0, len(keys), 100):
            resp = self.responses.meta.client.batch_get_item(
                RequestItems={self.responses.name: {"Keys": keys[start : start + 100]}}
            )
            for r in resp["Responses"].get(self.responses.name, []):
                found[_int(r["assessment_item_id"])] = self._response_dto(r)
        return found

    def create_response(
        self,
        *,
        student_id,
        item,
        challenge_id: int,
        response: str,
        score: float,
        scored_by: str,
        ai_feedback: str | None = None,
    ) -> AssessmentResponseDTO | None:
        raw = _prune(
            {
                "student_id": student_id,
                "assessment_item_id": item.id,
                "id": self._next_id("response"),
                # Denormalized for the ByChallenge index the outcome report reads.
                "challenge_id": challenge_id,
                "response": response,
                # _enc turns the float into a Decimal — boto3 refuses floats outright.
                "score": _enc(score),
                "scored_by": scored_by,
                "ai_feedback": ai_feedback,
                "ts": _enc(_now()),
            }
        )
        try:
            # The key IS uq_response_student_item, so the one-attempt rule is the write
            # itself: race-safe, where a read-then-write would not be.
            self.responses.put_item(
                Item=raw, ConditionExpression="attribute_not_exists(student_id)"
            )
        except self.responses.meta.client.exceptions.ConditionalCheckFailedException:
            return None
        return self._response_dto(raw)

    def _responses_for_item(self, item_id: int) -> list[dict]:
        return self._query_all(
            self.responses,
            IndexName="ByItem",
            KeyConditionExpression=Key("assessment_item_id").eq(item_id),
            ScanIndexForward=False,  # ts DESC, as the SQL query orders
        )

    def list_item_responses(self, item_id: int):
        rows = self._responses_for_item(item_id)
        if not rows:
            return []
        ids = list({r["student_id"] for r in rows})
        found: dict[str, StudentDTO] = {}
        for start in range(0, len(ids), 100):
            resp = self.students.meta.client.batch_get_item(
                RequestItems={
                    self.students.name: {
                        "Keys": [{"student_id": s} for s in ids[start : start + 100]]
                    }
                }
            )
            for s in resp["Responses"].get(self.students.name, []):
                found[s["student_id"]] = self._student_dto(s)
        return [
            (self._response_dto(r), found[r["student_id"]])
            for r in rows
            if r["student_id"] in found
        ]

    def get_item_response(self, item_id: int, response_id: int):
        # Filter on the exposed int id over one item's responses (~200, admin path) —
        # the same trade as get_checkin, and no extra index to maintain.
        for raw in self._responses_for_item(item_id):
            if _int(raw.get("id", 0)) == response_id:
                return self._response_dto(raw)
        return None

    def override_response_score(self, response, score: float):
        self.responses.update_item(
            Key={
                "student_id": response.student_id,
                "assessment_item_id": response.assessment_item_id,
            },
            UpdateExpression="SET score = :s, scored_by = :b",
            ExpressionAttributeValues={":s": _enc(score), ":b": "human"},
        )
        # ai_feedback is deliberately untouched — see the service's docstring.
        return AssessmentResponseDTO(
            id=response.id,
            student_id=response.student_id,
            assessment_item_id=response.assessment_item_id,
            response=response.response,
            score=score,
            scored_by="human",
            ai_feedback=response.ai_feedback,
            ts=response.ts,
        )

    def record_content_view(self, *, student_id, task, content_ref: str) -> None:
        ts = _now()
        self.views.put_item(
            Item={
                "challenge_id": task.challenge_id,
                # The uuid suffix is what implements "no unique constraint": a week can
                # only be completed once but read any number of times, and re-reading is
                # engagement rather than a duplicate to collapse (models/engagement.py).
                "view_id": f"{ts.isoformat()}#{uuid4().hex[:8]}",
                "student_id": student_id,
                "task_id": task.id,
                "content_ref": content_ref,
                "ts": _enc(ts),
            }
        )

    def count_content_views(self, challenge_id: int) -> dict[str, int]:
        # Partitioned by challenge, so this is one query — no fan-out. The biggest read
        # in the app (views, not viewers), which _query_all paginates if it needs to.
        counts: dict[str, int] = {}
        for raw in self._query_all(
            self.views, KeyConditionExpression=Key("challenge_id").eq(challenge_id)
        ):
            ref = raw["content_ref"]
            counts[ref] = counts.get(ref, 0) + 1
        return counts

    # --- Manual completion override + audit (FR-D6 / US-27) -----------------
    @staticmethod
    def _checkin_dto(raw: dict) -> CheckInDTO:
        return CheckInDTO(
            id=_int(raw["id"]),
            student_id=raw["student_id"],
            task_id=_int(raw["task_id"]),
            ts=_dt(raw.get("ts")),
            method=raw["method"],
            verified_by=raw.get("verified_by"),
        )

    @staticmethod
    def _audit_dto(raw: dict) -> CheckInAuditDTO:
        return CheckInAuditDTO(
            id=_int(raw["id"]),
            campus_id=raw["campus_id"],
            student_id=raw["student_id"],
            task_id=_int(raw["task_id"]),
            checkin_id=_int(raw["checkin_id"]) if raw.get("checkin_id") else None,
            action=raw["action"],
            actor_subject=raw["actor_subject"],
            reason=raw["reason"],
            ts=_dt(raw.get("ts")),
            prior_state=raw.get("prior_state"),
            new_state=raw.get("new_state"),
        )

    def _checkins_for_task(self, task_id: int) -> list[dict]:
        return self._query_all(
            self.checkins,
            IndexName="ByTask",
            KeyConditionExpression=Key("task_id").eq(task_id),
            ScanIndexForward=False,  # ts DESC — newest first, as the SQL query orders
        )

    def get_checkin(self, task_id: int, checkin_id: int) -> CheckInDTO | None:
        # Filter on the exposed int id over the task's own check-ins (~200 rows on an
        # admin path). No ById GSI: a third index to save one in-memory scan of a cold
        # path isn't worth its write cost — add one if this ever shows up in a trace.
        for raw in self._checkins_for_task(task_id):
            if _int(raw.get("id", 0)) == checkin_id:
                return self._checkin_dto(raw)
        return None

    def list_task_checkins(self, task_id: int) -> list[tuple[CheckInDTO, StudentDTO]]:
        rows = self._checkins_for_task(task_id)
        if not rows:
            return []
        # One batched read for the students, rather than a point read per check-in —
        # the Dynamo analogue of the SQL join.
        ids = list({r["student_id"] for r in rows})
        found: dict[str, StudentDTO] = {}
        for start in range(0, len(ids), 100):
            chunk = ids[start : start + 100]
            resp = self.students.meta.client.batch_get_item(
                RequestItems={
                    self.students.name: {"Keys": [{"student_id": sid} for sid in chunk]}
                }
            )
            for s in resp["Responses"].get(self.students.name, []):
                found[s["student_id"]] = self._student_dto(s)
        return [
            (self._checkin_dto(r), found[r["student_id"]])
            for r in rows
            if r["student_id"] in found
        ]

    def count_task_checkins(self, task_id: int) -> int:
        """How many students have checked in for a task (FR-D4 / US-28).

        ``Select="COUNT"`` returns a number with no items, so the live dashboard's 5s
        poll costs one query and no payload rather than shipping ~200 rows to be
        counted client-side. Still paginates: Dynamo counts at most 1 MB per page.
        """
        total = 0
        kwargs: dict[str, Any] = {
            "IndexName": "ByTask",
            "KeyConditionExpression": Key("task_id").eq(task_id),
            "Select": "COUNT",
        }
        resp = self.checkins.query(**kwargs)
        total += resp["Count"]
        while "LastEvaluatedKey" in resp:
            resp = self.checkins.query(
                ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs
            )
            total += resp["Count"]
        return total

    def list_recent_task_checkins(self, task_id: int, limit: int) -> list[CheckInDTO]:
        """The newest ``limit`` check-ins for a task, newest first.

        ``ts`` is the ByTask range key, so ``ScanIndexForward=False`` + ``Limit`` makes
        the index do the ordering and the truncation: Dynamo reads ~6 rows rather than
        the task's whole history. No Students read — the caller is the projected screen.
        """
        resp = self.checkins.query(
            IndexName="ByTask",
            KeyConditionExpression=Key("task_id").eq(task_id),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._checkin_dto(r) for r in resp.get("Items", [])]

    def list_task_audits(self, task_id: int, student_id=None) -> list[CheckInAuditDTO]:
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("task_id").eq(task_id),
            # The sort key encodes the timestamp, so newest-first is the index order —
            # matching the SQL order_by(ts.desc(), id.desc()) including the tie-break.
            "ScanIndexForward": False,
        }
        if student_id is not None:
            kwargs["FilterExpression"] = Attr("student_id").eq(student_id)
        return [self._audit_dto(r) for r in self._query_all(self.audits, **kwargs)]

    def _audit_item(
        self,
        *,
        campus_id: str,
        action: str,
        student_id,
        task_id: int,
        checkin_id: int | None,
        actor_subject: str,
        reason: str,
        prior: dict | None,
        new: dict | None,
    ) -> dict:
        audit_id = self._next_id("audit")
        ts = _now()
        return _prune(
            {
                "task_id": task_id,
                # ts#id: sorts the ledger by time, the id breaking ties within a
                # timestamp, so the query needs no in-app sort.
                "audit_id": f"{ts.isoformat()}#{audit_id}",
                "id": audit_id,
                "campus_id": campus_id,
                "student_id": student_id,
                "checkin_id": checkin_id,
                "action": action,
                "actor_subject": actor_subject,
                "reason": reason,
                "ts": _enc(ts),
                "prior_state": prior,
                "new_state": new,
            }
        )

    def _transact(self, items: list[dict]) -> None:
        """Write the check-in change and its audit row as one transaction.

        services/checkins.py names the invariant: a completion must never change
        without leaving a trace. On SQL that is one commit; here the two rows live in
        different tables, so only TransactWriteItems can promise it. Two put_items
        could half-apply and the ledger would quietly lie.
        """
        self.checkins.meta.client.transact_write_items(TransactItems=items)

    def create_manual_checkin(
        self,
        *,
        campus_id: str,
        task,
        student,
        actor_subject: str,
        reason: str,
        ts: datetime | None = None,
    ) -> CheckInDTO:
        item = _prune(
            {
                "student_id": student.id,
                "task_id": task.id,
                "id": self._next_id("checkin"),
                "challenge_id": task.challenge_id,
                "ts": _enc(ts or _now()),
                "method": "manual",
                "verified_by": actor_subject,
            }
        )
        dto = self._checkin_dto(item)
        audit = self._audit_item(
            campus_id=campus_id,
            action="create",
            student_id=student.id,
            task_id=task.id,
            checkin_id=dto.id,
            actor_subject=actor_subject,
            reason=reason,
            prior=None,
            new=checkin_snapshot(dto, student),
        )
        try:
            self._transact(
                [
                    {
                        "Put": {
                            "TableName": self.checkins.name,
                            "Item": item,
                            # The Dynamo form of uq_checkin_student_task: the condition
                            # is part of the transaction, so the duplicate check cannot
                            # race the write the way a read-then-write would.
                            "ConditionExpression": "attribute_not_exists(student_id)",
                        }
                    },
                    {"Put": {"TableName": self.audits.name, "Item": audit}},
                ]
            )
        except self.checkins.meta.client.exceptions.TransactionCanceledException as exc:
            reasons = exc.response.get("CancellationReasons") or []
            if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                raise ValueError("Student already has a check-in for this task") from exc
            raise
        return dto

    def correct_checkin(
        self,
        *,
        campus_id: str,
        checkin,
        student,
        actor_subject: str,
        reason: str,
        method: str | None = None,
        ts: datetime | None = None,
    ) -> CheckInDTO:
        prior = checkin_snapshot(checkin, student)
        updated = CheckInDTO(
            id=checkin.id,
            student_id=checkin.student_id,
            task_id=checkin.task_id,
            ts=ts or checkin.ts,
            method=method or checkin.method,
            verified_by=actor_subject,
        )
        audit = self._audit_item(
            campus_id=campus_id,
            action="update",
            student_id=checkin.student_id,
            task_id=checkin.task_id,
            checkin_id=checkin.id,
            actor_subject=actor_subject,
            reason=reason,
            prior=prior,
            new=checkin_snapshot(updated, student),
        )
        self._transact(
            [
                {
                    "Update": {
                        "TableName": self.checkins.name,
                        "Key": {
                            "student_id": checkin.student_id,
                            "task_id": checkin.task_id,
                        },
                        # An Update, not a Put: it leaves challenge_id and id in place
                        # without re-reading the row to copy them forward.
                        "UpdateExpression": ("SET #m = :m, #t = :t, verified_by = :v"),
                        "ExpressionAttributeNames": {"#m": "method", "#t": "ts"},
                        "ExpressionAttributeValues": {
                            ":m": updated.method,
                            ":t": _enc(updated.ts),
                            ":v": actor_subject,
                        },
                    }
                },
                {"Put": {"TableName": self.audits.name, "Item": audit}},
            ]
        )
        return updated

    def remove_checkin(
        self, *, campus_id: str, checkin, student, actor_subject: str, reason: str
    ) -> None:
        audit = self._audit_item(
            campus_id=campus_id,
            action="delete",
            student_id=checkin.student_id,
            task_id=checkin.task_id,
            checkin_id=checkin.id,
            actor_subject=actor_subject,
            reason=reason,
            # The snapshot is what survives the row.
            prior=checkin_snapshot(checkin, student),
            new=None,
        )
        self._transact(
            [
                {
                    "Delete": {
                        "TableName": self.checkins.name,
                        "Key": {
                            "student_id": checkin.student_id,
                            "task_id": checkin.task_id,
                        },
                    }
                },
                {"Put": {"TableName": self.audits.name, "Item": audit}},
            ]
        )

    # --- Themes -------------------------------------------------------------
    @staticmethod
    def _theme_dto(raw: dict) -> ThemeDTO:
        return ThemeDTO(
            id=raw["id"],
            name=raw["name"],
            palette=dict(raw.get("palette") or {}),
            logo_url=raw.get("logo_url"),
            hero_url=raw.get("hero_url"),
            app_title=raw.get("app_title", "Wellness Passport"),
            tagline=raw.get("tagline", ""),
            copy_tone=raw.get("copy_tone", ""),
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
        )

    def list_themes(self) -> list[ThemeDTO]:
        # <20 admin presets read from an admin screen: a Scan + in-app sort by name,
        # not a GSI that would buy nothing. The one Scan in this repository.
        items: list[dict] = []
        resp = self.themes.scan()
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = self.themes.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        items.sort(key=lambda r: r.get("name", ""))
        return [self._theme_dto(r) for r in items]

    def get_theme(self, theme_id: str) -> ThemeDTO | None:
        raw = self.themes.get_item(Key={"id": theme_id}).get("Item")
        return self._theme_dto(raw) if raw else None

    def create_theme(self, data: ThemeCreate) -> ThemeDTO:
        now = _now()
        item = _prune(
            {
                "id": data.id,
                "name": data.name,
                "palette": data.palette,
                "logo_url": data.logo_url,
                "hero_url": data.hero_url,
                "app_title": data.app_title,
                "tagline": data.tagline,
                "copy_tone": data.copy_tone,
                "created_at": _enc(now),
                "updated_at": _enc(now),
            }
        )
        # attribute_not_exists so a racing create cannot silently overwrite an existing
        # theme — the router 409s on the common case; this closes the race window.
        self.themes.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
        return self._theme_dto(item)

    def update_theme(self, theme_id: str, data: ThemeUpdate) -> ThemeDTO | None:
        raw = self.themes.get_item(Key={"id": theme_id}).get("Item")
        if raw is None:
            return None
        # exclude_unset: only fields the admin actually sent. A field sent as null
        # (clearing logo_url, say) becomes None here and is dropped by _prune — the
        # attribute is removed and reads back as null, matching the SQL updater.
        for field, value in data.model_dump(exclude_unset=True).items():
            raw[field] = _enc(value)
        raw["updated_at"] = _enc(_now())
        self.themes.put_item(Item=_prune(raw))
        return self._theme_dto(raw)

    def _theme_config(self, theme_id: str) -> ThemeConfigView | None:
        """Resolve a challenge's theme_id to the skin the passport carries (FR-B4).

        Mirrors services/passport._resolve_theme on the SQL path: an empty or dangling
        id degrades to the default skin (None), and it is read on every passport build
        so an admin's edit shows up on the student's next fetch (US-13 scenario 3).
        """
        if not theme_id:
            return None
        raw = self.themes.get_item(Key={"id": theme_id}).get("Item")
        if raw is None:
            return None
        return ThemeConfigView(
            id=raw["id"],
            palette=dict(raw.get("palette") or {}),
            logo_url=raw.get("logo_url"),
            hero_url=raw.get("hero_url"),
            app_title=raw.get("app_title", "Wellness Passport"),
            tagline=raw.get("tagline", ""),
            copy_tone=raw.get("copy_tone", ""),
        )

    # --- Passport -----------------------------------------------------------
    def _completed_task_ids(self, student_id, task_ids: set[int]) -> set[int]:
        # The exact (student_id, task_id) keys are known — this challenge's tasks — so
        # BatchGetItem fetches only those rows, rather than querying the student's whole
        # check-in history across every challenge and intersecting in Python (which grew
        # unboundedly with each past challenge). ProjectionExpression trims to the keys.
        if not task_ids:
            return set()
        keys = [{"student_id": student_id, "task_id": tid} for tid in task_ids]
        found: set[int] = set()
        # BatchGetItem caps at 100 keys/request; a challenge has ~6 tasks, but chunk
        # to stay correct if that ever grows.
        for start in range(0, len(keys), 100):
            chunk = keys[start : start + 100]
            resp = self.checkins.meta.client.batch_get_item(
                RequestItems={
                    self.checkins.name: {
                        "Keys": chunk,
                        "ProjectionExpression": "task_id",
                    }
                }
            )
            for r in resp["Responses"].get(self.checkins.name, []):
                found.add(_int(r["task_id"]))
        return found

    def build_passport_for(self, challenge: ChallengeDTO, student_id) -> PassportView:
        """Assemble the passport for an already-resolved active challenge.

        Split out so a caller that already holds the challenge reuses it instead of
        re-querying ``get_active_challenge``: the QR scan path (which just validated it
        against the token) and /api/bootstrap (which needs it for the enrollment answer).
        """
        tasks = self._tasks_for_challenge(challenge.id)
        completed = self._completed_task_ids(student_id, {t.id for t in tasks})
        return assemble_passport(
            challenge_name=challenge.name,
            theme=challenge.theme_id,
            tasks=tasks,
            completed_ids=completed,
            theme_config=self._theme_config(challenge.theme_id),
        )

    def build_passport(self, campus_id: str, student_id) -> PassportView | None:
        challenge = self.get_active_challenge(campus_id)
        if challenge is None:
            return None
        return self.build_passport_for(challenge, student_id)

    def _create_checkin(
        self, student_id, task_id: int, challenge_id: int, method: str
    ) -> bool:
        """Insert a check-in; return False if the student already has one (idempotent).

        Carries the GSI keys every admin/report read needs: ``id`` (the int the API
        exposes), ``challenge_id`` (denormalized off the task, the ByChallenge hash)
        and ``ts`` (the ByTask/ByChallenge range). A row missing any of them would be
        invisible to those indexes — no error, just absent.
        """
        try:
            self.checkins.put_item(
                Item=_prune(
                    {
                        "student_id": student_id,
                        "task_id": task_id,
                        "id": self._next_id("checkin"),
                        "challenge_id": challenge_id,
                        "ts": _enc(_now()),
                        "method": method,
                    }
                ),
                ConditionExpression="attribute_not_exists(student_id)",
            )
            return True
        except self.checkins.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    def record_event_qr_checkin(
        self, campus_id: str, student_id, token: str
    ) -> tuple[TaskDTO, PassportView]:
        task_id = verify_event_token(token)
        if task_id is None:
            raise InvalidEventToken
        challenge = self.get_active_challenge(campus_id)
        if challenge is None:
            raise InvalidEventToken
        raw = self.tasks.get_item(Key={"id": task_id}).get("Item")
        if raw is None or _int(raw.get("challenge_id")) != challenge.id:
            raise InvalidEventToken
        if not self._create_checkin(student_id, task_id, challenge.id, "event_qr"):
            raise DuplicateCheckIn
        # Reuse the challenge already resolved above for the refreshed passport, so the
        # scan path resolves the active challenge once rather than twice.
        return self._task_dto(raw), self.build_passport_for(challenge, student_id)
