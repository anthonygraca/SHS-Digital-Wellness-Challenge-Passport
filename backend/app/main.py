from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routers import auth, challenges, enrollment, passport

# Built SPA lives at repo-root/frontend/dist. main.py is backend/app/main.py, so
# the repo root is parents[2]. Resolved from __file__ (not cwd) so it works no
# matter where uvicorn is launched from.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only the SQL backend creates tables + seeds at startup. On the Dynamo path the
    # tables are provisioned by SAM and seeded by scripts/seed_dynamo.py, so there is
    # nothing to do here. (This local all-routers app is used by `make dev`/uvicorn;
    # Lambda uses the per-function apps in app/functions, which have no lifespan.)
    if get_settings().persistence == "sql":
        init_db()
    yield


app = FastAPI(title="SHS Wellness Passport API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(enrollment.router)
app.include_router(challenges.router)
app.include_router(passport.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# Single-origin production serving: uvicorn serves the built SPA alongside the API
# so the QR camera + PWA get a secure HTTPS context off-localhost (see
# scripts/deploy-https.sh). Registered LAST so the API routers above win. Hashed
# build assets are mounted; the catch-all returns any other real file in dist
# (sw.js, manifest, icons) and otherwise falls back to index.html for client-side
# routes (e.g. /auth/callback, /passport). Guarded so dev — where dist may be
# unbuilt — still boots the API alone.
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = (DIST / full_path).resolve()
        # Serve real files that live inside dist; reject path traversal.
        if full_path and DIST in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
