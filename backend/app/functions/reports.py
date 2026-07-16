"""reports-fn — cohort reporting + prize export (`/api/reports/*`)."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.reports import router

app = make_app(router, title="reports")
handler = Mangum(app)
