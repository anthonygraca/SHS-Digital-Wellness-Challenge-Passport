"""assessments-fn — knowledge checks: MCQ + reflection scoring (`/api/assessments/*`)."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.assessments import router

app = make_app(router, title="assessments")
handler = Mangum(app)
