"""The SPA mount — SpaStaticFiles' fallback, and the paths it must NOT swallow.

Binds the first two acceptance scenarios from TD-5 (#54):

    Scenario: The SPA and API are served as one artifact
      ... client-side routes resolve on a direct load or a refresh

    Scenario: An API miss is not answered with the app shell
      When a client requests an API path that does not exist
      Then it receives a JSON 404 rather than HTML at status 200

Why this builds its own app rather than using the `client` fixture: app/main.py
mounts the SPA only `if STATIC_DIR.is_dir()`, and that directory exists only
inside the container image, where the Dockerfile copies the built dist/ into it.
A test that imported the real app would silently assert nothing at all — the
mount would not be there, every request would 404, and the suite would be green
while proving the opposite of what it claims. So these mount SpaStaticFiles
against a throwaway directory and exercise the class itself.

This mount has been reverted by a merge once already (#54). It builds fine when
it is gone; only the UI disappears. release.sh checks for HTML at / as a last
line of defence, but that fires after a push — this fires in CI.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import SpaStaticFiles

SHELL = "<!doctype html><title>app shell</title>"


@pytest.fixture
def spa_client(tmp_path):
    (tmp_path / "index.html").write_text(SHELL)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('real asset')")

    app = FastAPI()

    # Stand-ins for the real app's registered routes: the mount is last, so it
    # only ever sees what the routers did not match.
    @app.get("/api/challenges")
    def _challenges():
        return {"ok": True}

    @app.get("/healthz")
    def _healthz():
        return {"status": "ok"}

    app.mount("/", SpaStaticFiles(directory=tmp_path, html=True), name="spa")
    return TestClient(app)


def test_serves_index_at_root(spa_client):
    res = spa_client.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")


def test_serves_real_assets_from_disk(spa_client):
    """The fallback must not shadow files that actually exist."""
    res = spa_client.get("/assets/app.js")
    assert res.status_code == 200
    assert "real asset" in res.text


@pytest.mark.parametrize("route", ["/home", "/passport", "/admin", "/admin/reports"])
def test_client_side_routes_fall_back_to_the_shell(spa_client, route):
    """React Router owns these; none exist as files. A direct load or refresh
    must get the shell rather than a 404."""
    res = spa_client.get(route)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert res.text == SHELL


def test_auth_callback_falls_back(spa_client):
    """/auth is deliberately NOT in _API_ONLY_PREFIXES.

    The API's /auth routes are all registered, so the only unmatched /auth path
    is /auth/callback — genuinely client-side, and where sign-in lands. Excluding
    /auth to "be consistent" with the other API prefixes dead-ends login.
    """
    res = spa_client.get("/auth/callback")
    assert res.status_code == 200
    assert res.text == SHELL


def test_registered_api_routes_still_win(spa_client):
    """The mount is last and must not shadow a real route."""
    assert spa_client.get("/api/challenges").json() == {"ok": True}
    assert spa_client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/nope",
        "/api/challenges/99999/nope",
        "/enrollment/nope",
        "/mock-idp/nope",
        "/healthz/nope",
    ],
)
def test_api_misses_stay_json_404_and_never_become_the_shell(spa_client, path):
    """The bug this prevents: the shell returned at HTTP 200 for an API miss.

    An API client's `res.ok` check passes, and res.json() then chokes on HTML —
    surfacing far from the cause, as "we couldn't load your challenge". The same
    trap is documented for the dev proxy in frontend/vite.config.ts.
    """
    res = spa_client.get(path)
    assert res.status_code == 404
    assert not res.headers["content-type"].startswith("text/html")
    assert res.text != SHELL
