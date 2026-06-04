"""
Shared pytest fixtures for Sprint 0 tests.

Each test gets a fresh Flask test client and a clean in-memory db.json
so tests never interfere with each other or with real stored data.
"""

import json
import pytest
from unittest.mock import patch

from server import create_app

EMPTY_DB = {"projects": {}, "artifacts": {}, "versions": {}, "reviews": {}}


@pytest.fixture
def client(tmp_path):
    """
    Provide a Flask test client backed by an isolated db.json in tmp_path.
    Filesystem side-effects (makedirs) are suppressed.
    """
    db_file = tmp_path / "db.json"
    db_file.write_text(json.dumps(EMPTY_DB))

    app = create_app()
    app.config["TESTING"] = True

    with patch("storage.store.DB_PATH", str(db_file)), \
         patch("storage.store._ensure_version_dir"), \
         patch("storage.store._ensure_review_dir"):
        with app.test_client() as c:
            yield c
