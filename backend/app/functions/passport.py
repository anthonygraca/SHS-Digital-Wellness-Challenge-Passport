"""passport-fn — passport read + QR check-in (`/api/passport`, `/api/checkins/scan`)."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.passport import router

app = make_app(router, title="passport")
handler = Mangum(app)
