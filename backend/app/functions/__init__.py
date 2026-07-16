"""Per-route Lambda entrypoints.

Each module here builds a slim FastAPI app that includes exactly ONE router and wraps
it with Mangum, so API Gateway can route each path prefix to its own function with
its own IAM. `make_app` is the shared factory; the local all-routers app for
`make dev` / uvicorn still lives in `app.main`.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI


def make_app(router: APIRouter | None = None, *, title: str) -> FastAPI:
    """Build a single-router FastAPI app for a Lambda function.

    No lifespan/`init_db`: on the Dynamo path tables are provisioned by SAM, not at
    cold start. Every function also answers `/healthz` for cheap per-function probes.
    """
    app = FastAPI(title=f"SHS Wellness Passport — {title}")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    if router is not None:
        app.include_router(router)
    return app
