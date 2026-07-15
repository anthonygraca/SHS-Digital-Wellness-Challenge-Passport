from __future__ import annotations

"""Tests for FR-B4 / NFR-6 (US-13): theme selection and re-skin.

Same fixture pattern as test_challenges.py: in-memory SQLite, TestClient,
dependency_overrides[get_db]. Note the fixture bypasses init_db, so the seeded
presets do not exist here — tests create the themes they need via the API.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = "user@csub.edu") -> None:
    """Authenticate via the mock IdP ACS and store the session cookie."""
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _create_theme(client, **overrides):
    payload = {
        "id": "stranger-things",
        "name": "Stranger Things",
        "palette": {"primary": "#ff4438", "hero-a": "#4a0f0a"},
        "logo_url": "https://cdn.example.edu/st-logo.png",
        "hero_url": "https://cdn.example.edu/st-hero.jpg",
        "app_title": "Wellness Passport",
        "tagline": "Step through the first portal.",
        "copy_tone": "dark, retro-80s, ominous",
        **overrides,
    }
    return client.post("/api/themes", json=payload)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateTheme:
    def test_admin_creates_theme(self, client):
        _sign_in_as(client, "staff")
        resp = _create_theme(client)

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "stranger-things"
        assert body["name"] == "Stranger Things"
        assert body["palette"] == {"primary": "#ff4438", "hero-a": "#4a0f0a"}
        assert body["logo_url"] == "https://cdn.example.edu/st-logo.png"
        assert body["hero_url"] == "https://cdn.example.edu/st-hero.jpg"
        assert body["tagline"] == "Step through the first portal."
        assert body["copy_tone"] == "dark, retro-80s, ominous"

    def test_duplicate_id_rejected(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)
        assert _create_theme(client).status_code == 409

    def test_non_slug_id_rejected(self, client):
        _sign_in_as(client, "staff")
        assert _create_theme(client, id="Stranger Things!").status_code == 422


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestReadTheme:
    def test_list_returns_created_themes(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)
        _create_theme(client, id="harry-potter", name="Harry Potter")

        resp = client.get("/api/themes")
        assert resp.status_code == 200
        assert {t["id"] for t in resp.json()} == {"stranger-things", "harry-potter"}

    def test_get_single_theme(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)
        resp = client.get("/api/themes/stranger-things")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Stranger Things"

    def test_unknown_theme_404(self, client):
        _sign_in_as(client, "staff")
        assert client.get("/api/themes/nope").status_code == 404


# ---------------------------------------------------------------------------
# Update — "Edit theme attributes" (US-13 scenario 3)
# ---------------------------------------------------------------------------


class TestUpdateTheme:
    def test_partial_update_leaves_other_fields_alone(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)

        resp = client.patch(
            "/api/themes/stranger-things", json={"tagline": "The portal is open."}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tagline"] == "The portal is open."
        assert body["palette"] == {"primary": "#ff4438", "hero-a": "#4a0f0a"}
        assert body["name"] == "Stranger Things"

    def test_palette_is_replaced_wholesale(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)

        resp = client.patch(
            "/api/themes/stranger-things", json={"palette": {"primary": "#00ff00"}}
        )
        assert resp.status_code == 200
        assert resp.json()["palette"] == {"primary": "#00ff00"}

    def test_asset_url_can_be_cleared(self, client):
        _sign_in_as(client, "staff")
        _create_theme(client)

        resp = client.patch("/api/themes/stranger-things", json={"logo_url": None})
        assert resp.status_code == 200
        assert resp.json()["logo_url"] is None
        # hero_url was not in the payload, so it survives untouched.
        assert resp.json()["hero_url"] == "https://cdn.example.edu/st-hero.jpg"

    def test_update_unknown_theme_404(self, client):
        _sign_in_as(client, "staff")
        assert client.patch("/api/themes/nope", json={"tagline": "x"}).status_code == 404


# ---------------------------------------------------------------------------
# RBAC — themes are admin-only
# ---------------------------------------------------------------------------


class TestThemeAccessControl:
    def test_unauthenticated_is_401(self, client):
        assert client.get("/api/themes").status_code == 401
        assert _create_theme(client).status_code == 401
        assert client.patch("/api/themes/x", json={"tagline": "y"}).status_code == 401

    def test_student_is_403(self, client):
        _sign_in_as(client, "student")
        assert client.get("/api/themes").status_code == 403
        assert _create_theme(client).status_code == 403
        assert client.patch("/api/themes/x", json={"tagline": "y"}).status_code == 403
