"""enrollment-fn — join a challenge (`/enrollment`). Current-student gated."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.enrollment import router

app = make_app(router, title="enrollment")
handler = Mangum(app)
