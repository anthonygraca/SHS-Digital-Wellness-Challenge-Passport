from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import auth, challenges


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SHS Wellness Passport API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(challenges.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
