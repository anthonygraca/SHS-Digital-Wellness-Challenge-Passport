"""auth-fn — SSO login/session (`/auth/*`, `/mock-idp/*`). Public; touches Students."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.auth import router

app = make_app(router, title="auth")
handler = Mangum(app)
