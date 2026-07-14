from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Student(Base):
    """Minimal student identity (FR-A2).

    Stores ONLY an opaque SSO subject + affiliation, scoped by campus. There are
    deliberately no name, 9-digit ID, password, or any PHI columns — the schema
    itself is the privacy guarantee. Uniqueness is guaranteed by the IdP subject.
    """

    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("campus_id", "sso_subject", name="uq_student_campus_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sso_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    affiliation: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
