"""themes-fn — theme presets admin CRUD (`/api/themes`, `/api/themes/{proxy+}`)."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.themes import router

app = make_app(router, title="themes")
handler = Mangum(app)
