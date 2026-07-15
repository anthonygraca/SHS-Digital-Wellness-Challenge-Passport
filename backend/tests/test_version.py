"""GET /api/version — what commit is actually deployed here.

The endpoint exists because release.sh tags images by git SHA but a *running*
deployment had no way to say which SHA it was; you had to go read ECR.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.main import APP_VERSION


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    """get_settings is lru_cached, so env set inside a test is otherwise ignored."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_reports_the_app_version(client):
    body = client.get("/api/version").json()
    assert body["version"] == APP_VERSION


def test_unstamped_build_says_unknown_rather_than_guessing(client):
    """A plain `docker build` or a local uvicorn passes no build args.

    "unknown" is the correct answer there. The failure this guards against is a
    default that looks like real provenance — reporting a stale hard-coded SHA,
    or the string "latest", would make an unstamped build indistinguishable from
    a stamped one at exactly the moment you are trying to tell them apart.
    """
    body = client.get("/api/version").json()
    assert body["gitSha"] == "unknown"
    assert body["builtAt"] == "unknown"


def test_reports_the_stamped_sha_and_build_time(client, monkeypatch):
    monkeypatch.setenv("WP_GIT_SHA", "abc1234-dirty")
    monkeypatch.setenv("WP_BUILT_AT", "2026-07-15T12:00:00Z")
    get_settings.cache_clear()

    body = client.get("/api/version").json()
    assert body["gitSha"] == "abc1234-dirty"
    assert body["builtAt"] == "2026-07-15T12:00:00Z"


def test_needs_no_session(client):
    """Diagnosing a deployment must not require signing in to it."""
    assert client.get("/api/version").status_code == 200
