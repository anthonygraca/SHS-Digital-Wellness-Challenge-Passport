"""challenges-fn — admin ChallengeBuilder (`/api/challenges/*`). Admin gated."""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.challenges import router

app = make_app(router, title="challenges")
handler = Mangum(app)
