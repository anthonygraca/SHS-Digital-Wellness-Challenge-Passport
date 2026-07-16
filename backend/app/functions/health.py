"""health-fn — public `/healthz` probe. No routers, no table access."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app

app = make_app(title="health")
handler = Mangum(app)
