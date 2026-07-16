"""End-to-end check of scripts/seed_dynamo.py against a moto-mocked DynamoDB.

Confirms the one-off seed creates the demo challenge (published, themed) with its 7
tasks and is idempotent on re-run — the Dynamo analogue of init_db -> seed_demo_challenge.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

from tests.ddb_support import dynamo_backend, set_env


def test_seed_dynamo_creates_demo_and_is_idempotent(monkeypatch):
    set_env(monkeypatch)

    from app.config import get_settings

    get_settings.cache_clear()
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))

    with dynamo_backend():
        from app.repositories.dynamo_repo import DynamoRepository, reset_tables

        reset_tables()
        import seed_dynamo

        importlib.reload(seed_dynamo)

        assert seed_dynamo.main() == 0
        assert seed_dynamo.main() == 0  # idempotent second run is a no-op

        repo = DynamoRepository()
        active = repo.get_active_challenge("csub")
        assert active is not None
        assert active.theme_id == "stranger-things"
        full = repo.get_challenge("csub", active.id)
        assert [t.position for t in full.tasks] == [1, 2, 3, 4, 5, 6, 7]

    reset_tables()
    get_settings.cache_clear()
