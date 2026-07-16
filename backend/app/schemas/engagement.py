from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# What a student can look at, and therefore what a ContentView row can record.
#
# "week_detail" — opening a week's detail sheet on the passport. UC-6 names this
# trigger explicitly ("A successful check-in (UC-3), or opening a week").
# "tip" — the personalized tip returned after an event-QR check-in (FR-E1).
#
# A Literal rather than a free string so an unknown ref is a 422 at the edge
# instead of a row the engagement report has no bucket for. The report's own
# reconciliation gap (services/reports.py) is the backstop for anything that
# reaches the table another way.
ContentRef = Literal["week_detail", "tip"]


class ContentViewCreate(BaseModel):
    """A student reporting that they looked at something (FR-F3 / US-23).

    camelCase to match the rest of the student-facing API (see schemas/passport.py
    — "Field names are camelCase for the SPA (no aliases)").

    ``weekNo`` rather than a task id: the passport never learns task ids, and
    resolving the week server-side against the campus's active challenge is what
    keeps a student from reporting a view of another campus's task.

    Only ``week_detail`` is ever posted here in practice. ``tip`` is written
    server-side by the scan route, which knows it delivered one — see
    routers/passport.py. The vocabulary is shared rather than split so the table
    has one definition of what a content ref is.
    """

    weekNo: int
    contentRef: ContentRef
