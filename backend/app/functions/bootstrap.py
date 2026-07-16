"""bootstrap-fn — the SPA's one-shot first-render payload (`/api/bootstrap`)."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.bootstrap import router

app = make_app(router, title="bootstrap")
handler = Mangum(app)
