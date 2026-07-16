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
    {prefix}Counters          PK name (S), attr seq (N)   [integer-id allocation]

DynamoDB has no constraints, so the SQL invariants are re-implemented here:
uniqueness/idempotency via conditional writes, cascade-delete + position renumber in
code, and integer ids via an atomic counter. The pure passport derivation and the QR
token + exceptions are shared with the SQL path (app.services.passport / .qr).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from app.config import get_settings
from app.repositories.dto import (
    AssessmentItemDTO,
    ChallengeDTO,
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
    """Encode a Python value for a DynamoDB attribute (dates -> ISO strings)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _prune(item: dict) -> dict:
    """Drop None values — DynamoDB attributes are simply absent rather than NULL."""
    return {k: v for k, v in item.items() if v is not None}


def _int(value: Any) -> int:
    return int(value) if isinstance(value, Decimal) else int(value)


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
        return StudentDTO(
            id=raw["student_id"],
            campus_id=raw["campus_id"],
            sso_subject=raw["sso_subject"],
            affiliation=raw["affiliation"],
            created_at=_dt(raw.get("created_at")),
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

    def _build_passport_for(self, challenge: ChallengeDTO, student_id) -> PassportView:
        """Assemble the passport for an already-resolved active challenge.

        Split out so the QR scan path can reuse the challenge it just validated instead
        of re-querying ``get_active_challenge`` a second time for the refreshed passport.
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
        return self._build_passport_for(challenge, student_id)

    def _create_checkin(self, student_id, task_id: int, method: str) -> bool:
        """Insert a check-in; return False if the student already has one (idempotent)."""
        try:
            self.checkins.put_item(
                Item={
                    "student_id": student_id,
                    "task_id": task_id,
                    "ts": _enc(_now()),
                    "method": method,
                },
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
        if not self._create_checkin(student_id, task_id, "event_qr"):
            raise DuplicateCheckIn
        # Reuse the challenge already resolved above for the refreshed passport, so the
        # scan path resolves the active challenge once rather than twice.
        return self._task_dto(raw), self._build_passport_for(challenge, student_id)
