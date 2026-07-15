from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.db import init_db
from app.routers import (
    assessments,
    auth,
    challenges,
    enrollment,
    guide,
    passport,
    reports,
    themes,
)

# The built SPA, copied here by the container image. Absent in local dev, where
# Vite serves the frontend and proxies these same paths back to this app.
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Paths the API owns outright. A miss under one of these is a genuine 404 and must
# stay a 404: answering it with index.html would hand an API client HTML at HTTP
# 200, whose res.ok check passes and whose res.json() then chokes. Note /auth is
# absent — the API's /auth routes are all registered below, so the only unmatched
# /auth path is /auth/callback, which really is a client-side route.
_API_ONLY_PREFIXES = ("api/", "enrollment", "mock-idp/", "healthz")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SHS Wellness Passport API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(enrollment.router)
app.include_router(challenges.router)
app.include_router(passport.router)
app.include_router(assessments.router)
app.include_router(reports.router)
app.include_router(themes.router)
app.include_router(guide.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


class SpaStaticFiles(StaticFiles):
    """Static files with a single-page-app fallback.

    React Router owns /auth/callback, /home, /passport and /admin/*; none of them
    exist as files on disk. A plain StaticFiles mount 404s on them, which breaks
    both a page refresh and the post-login redirect. Serve index.html instead and
    let the client router resolve the path.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith(_API_ONLY_PREFIXES):
                raise
            return await super().get_response("index.html", scope)


# Mounted last so every router above matches first; this only sees what the API
# does not own. Serving the SPA from the API's own origin is a requirement, not a
# convenience: the session cookie is SameSite=Lax and the client calls relative
# paths, so a split origin would silently drop the cookie and break sign-in.
if STATIC_DIR.is_dir():
    app.mount("/", SpaStaticFiles(directory=STATIC_DIR, html=True), name="spa")
