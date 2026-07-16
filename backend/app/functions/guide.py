"""guide-fn — the conversational wellness guide (`/api/guide/*`).

The only function here with no DynamoDB policy at all: the guide takes no ``db`` and
writes no transcript, deliberately (routers/guide.py explains why), so it has nothing
to be granted access to.
"""

from __future__ import annotations

from mangum import Mangum

from app.functions import make_app
from app.routers.guide import router

app = make_app(router, title="guide")
handler = Mangum(app)
