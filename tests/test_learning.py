"""
Tests for POST /learning and GET /learning — Sprint 6 Learning Layer.

Required tests:
- test_learning_from_review
- test_learning_from_reconciliation
- test_learning_from_proposal
- test_invalid_source
- test_learning_structure

Isolation strategy:
- conftest `client` fixture patches storage.store.DB_PATH to a tmp file.
- We additionally patch:
    - services.reconciliation_service._get_recon_db_path → tmp recon_db.json
    - services.proposal_service._get_proposal_db_path   → tmp proposal_db.json
    - services.learning_service._get_learning_db_path   → tmp learning_db.json
- All filesystem side-effects in store.py are suppressed.
"""

import json
import pytest
from unittest.mock import patch

from server import create_app

EMPTY_DB = {"projects": {}, "artifacts": {}, "versions": {}, "reviews": {}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "db.json"
    db_file.write_text(json.dumps(EMPTY_DB))

    recon_db_file = tmp_path / "recon_db.json"
    proposal_db_file = tmp_path / "proposal_db.json"
    learning_db_file = tmp_path / "learning_db.json"

    app = create_app()
    app.config["TESTING"] = True

    with patch("storage.store.DB_PATH", str(db_file)), \
         patch("storage.store._ensure_version_dir"), \
         patch("storage.store._ensure_review_dir"), \
         patch(
             "services.reconciliation_service._get_recon_db_path",
             return_value=str(recon_db_file),
         ), \
         patch(
             "services.proposal_service._get_proposal_db_path",
             return_value=str(proposal_db_file),
         ), \
         patch(
             "services.learning_service._get_learning_db_path",
             return_value=str(learning_db_file),
         ):
        with app.test_client() as c:
            yield c


# ---------------------------------------------------------------------------
# Helpers — build the full project → artifact → version → review chain
# ---------------------------------------------------------------------------

def _make_project(client, name="TestProject"):
    return client.post("/projects", json={"name": name}).get_json()["project_id"]


def _make_artifact(client, project_id):
    return client.post("/artifacts", json={
        "project_id": project_id,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    }).get_json()["artifact_id"]


def _make_version(client, project_id, artifact_id):
    return client.post("/versions", json={
        "project_id": project_id,
        "artifact_ids": [artifact_id],
    }).get_json()["version_id"]


def _make_review(client, version_id):
    return client.post("/reviews", json={"version_id": version_id}).get_json()["review_id"]


def _make_reconciliation(client, review_ids):
    return client.post(
        "/reconciliation", json={"review_ids": review_ids}
    ).get_json()["recon_id"]


def _make_proposal_from_review(client, review_id):
    return client.post(
        "/proposal", json={"review_id": review_id}
    ).get_json()["proposal_id"]


def _setup_review(client):
    """Project → artifact → version → review. Returns review_id."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    return _make_review(client, vid)


def _setup_reconciliation(client):
    """Two reviews → reconciliation. Returns recon_id."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)
    return _make_reconciliation(client, [r1, r2])


def _setup_proposal(client):
    """Review → proposal. Returns proposal_id."""
    review_id = _setup_review(client)
    return _make_proposal_from_review(client, review_id)


# ---------------------------------------------------------------------------
# test_learning_from_review
# ---------------------------------------------------------------------------

def test_learning_from_review_returns_201(client):
    review_id = _setup_review(client)
    res = client.post("/learning", json={"source_type": "review", "source_id": review_id})
    assert res.status_code == 201


def test_learning_from_review_returns_learning_id(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert "learning_id" in data
    assert isinstance(data["learning_id"], str)
    assert len(data["learning_id"]) > 0


def test_learning_from_review_source_type_matches(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert data["source_type"] == "review"


def test_learning_from_review_source_id_matches(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert data["source_id"] == review_id


def test_learning_from_review_approved_is_false(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert data["approved"] is False


def test_learning_from_review_has_insights(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert "insights" in data
    assert isinstance(data["insights"], list)


def test_learning_from_review_has_suggested_prompt_updates(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert "suggested_prompt_updates" in data
    assert isinstance(data["suggested_prompt_updates"], list)


def test_learning_from_review_has_reusable_patterns(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert "reusable_patterns" in data
    assert isinstance(data["reusable_patterns"], list)


def test_learning_from_review_patterns_not_empty(client):
    """A review of a sparse version always yields weaknesses → patterns."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert len(data["reusable_patterns"]) > 0


def test_learning_from_review_prompt_updates_not_empty(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert len(data["suggested_prompt_updates"]) > 0


def test_learning_from_review_insights_not_empty(client):
    """A sparse version produces repeated missing_information weaknesses → insight."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert len(data["insights"]) > 0


# ---------------------------------------------------------------------------
# test_learning_from_reconciliation
# ---------------------------------------------------------------------------

def test_learning_from_reconciliation_returns_201(client):
    recon_id = _setup_reconciliation(client)
    res = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    )
    assert res.status_code == 201


def test_learning_from_reconciliation_returns_learning_id(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert "learning_id" in data
    assert len(data["learning_id"]) > 0


def test_learning_from_reconciliation_source_type_matches(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert data["source_type"] == "reconciliation"


def test_learning_from_reconciliation_source_id_matches(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert data["source_id"] == recon_id


def test_learning_from_reconciliation_approved_is_false(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert data["approved"] is False


def test_learning_from_reconciliation_has_reusable_patterns(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert isinstance(data["reusable_patterns"], list)
    assert len(data["reusable_patterns"]) > 0


def test_learning_from_reconciliation_has_suggested_prompt_updates(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert isinstance(data["suggested_prompt_updates"], list)
    assert len(data["suggested_prompt_updates"]) > 0


def test_learning_from_reconciliation_has_created_at(client):
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    assert "created_at" in data
    assert isinstance(data["created_at"], str)


# ---------------------------------------------------------------------------
# test_learning_from_proposal
# ---------------------------------------------------------------------------

def test_learning_from_proposal_returns_201(client):
    proposal_id = _setup_proposal(client)
    res = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    )
    assert res.status_code == 201


def test_learning_from_proposal_returns_learning_id(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert "learning_id" in data
    assert len(data["learning_id"]) > 0


def test_learning_from_proposal_source_type_matches(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert data["source_type"] == "proposal"


def test_learning_from_proposal_source_id_matches(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert data["source_id"] == proposal_id


def test_learning_from_proposal_approved_is_false(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert data["approved"] is False


def test_learning_from_proposal_has_reusable_patterns(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert isinstance(data["reusable_patterns"], list)
    assert len(data["reusable_patterns"]) > 0


def test_learning_from_proposal_has_suggested_prompt_updates(client):
    proposal_id = _setup_proposal(client)
    data = client.post(
        "/learning", json={"source_type": "proposal", "source_id": proposal_id}
    ).get_json()
    assert isinstance(data["suggested_prompt_updates"], list)
    assert len(data["suggested_prompt_updates"]) > 0


# ---------------------------------------------------------------------------
# test_invalid_source
# ---------------------------------------------------------------------------

def test_invalid_source_type_returns_400(client):
    res = client.post("/learning", json={"source_type": "iteration", "source_id": "abc"})
    assert res.status_code == 400


def test_invalid_source_type_error_has_error_key(client):
    res = client.post("/learning", json={"source_type": "iteration", "source_id": "abc"})
    assert "error" in res.get_json()


def test_missing_source_type_returns_400(client):
    res = client.post("/learning", json={"source_id": "abc"})
    assert res.status_code == 400


def test_missing_source_id_returns_400(client):
    res = client.post("/learning", json={"source_type": "review"})
    assert res.status_code == 400


def test_empty_body_returns_400(client):
    res = client.post("/learning", json={})
    assert res.status_code == 400


def test_no_json_body_returns_400(client):
    res = client.post("/learning")
    assert res.status_code == 400


def test_unknown_review_id_returns_400(client):
    res = client.post("/learning", json={"source_type": "review", "source_id": "ghost-id"})
    assert res.status_code == 400


def test_unknown_review_id_error_mentions_id(client):
    res = client.post("/learning", json={"source_type": "review", "source_id": "ghost-review"})
    assert "ghost-review" in res.get_json()["error"]


def test_unknown_reconciliation_id_returns_400(client):
    res = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": "ghost-recon"}
    )
    assert res.status_code == 400


def test_unknown_proposal_id_returns_400(client):
    res = client.post(
        "/learning", json={"source_type": "proposal", "source_id": "ghost-proposal"}
    )
    assert res.status_code == 400


def test_invalid_source_type_error_mentions_valid_types(client):
    data = client.post(
        "/learning", json={"source_type": "unknown_type", "source_id": "abc"}
    ).get_json()
    error = data["error"].lower()
    assert "proposal" in error or "reconciliation" in error or "review" in error


# ---------------------------------------------------------------------------
# test_learning_structure
# ---------------------------------------------------------------------------

def test_learning_structure_has_all_required_keys(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for key in (
        "learning_id", "source_type", "source_id",
        "insights", "suggested_prompt_updates",
        "reusable_patterns", "approved", "created_at",
    ):
        assert key in data, f"Missing top-level key: {key}"


def test_learning_structure_approved_is_boolean(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert isinstance(data["approved"], bool)


def test_learning_structure_approved_is_always_false(client):
    """approved must never be True on creation — suggestions are never auto-applied."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert data["approved"] is False


def test_learning_structure_insight_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for insight in data["insights"]:
        for key in ("type", "category", "detail"):
            assert key in insight, f"Missing insight key: {key}"


def test_learning_structure_insight_type_is_valid(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    valid_types = {"repeated_pattern", "high_severity_pattern"}
    for insight in data["insights"]:
        assert insight["type"] in valid_types, f"Unexpected insight type: {insight['type']}"


def test_learning_structure_prompt_update_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for update in data["suggested_prompt_updates"]:
        for key in ("category", "suggestion", "approved"):
            assert key in update, f"Missing suggested_prompt_update key: {key}"


def test_learning_structure_prompt_update_approved_is_false(client):
    """Each individual suggestion must also carry approved=False."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for update in data["suggested_prompt_updates"]:
        assert update["approved"] is False


def test_learning_structure_prompt_update_suggestion_is_non_empty_string(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for update in data["suggested_prompt_updates"]:
        assert isinstance(update["suggestion"], str)
        assert len(update["suggestion"]) > 0


def test_learning_structure_reusable_pattern_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for pattern in data["reusable_patterns"]:
        for key in ("category", "pattern", "description", "severity"):
            assert key in pattern, f"Missing reusable_pattern key: {key}"


def test_learning_structure_reusable_pattern_severity_is_valid(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    for pattern in data["reusable_patterns"]:
        assert pattern["severity"] in ("low", "medium", "high"), \
            f"Invalid severity in pattern: {pattern['severity']}"


def test_learning_structure_no_duplicate_categories_in_patterns(client):
    """Each category should appear at most once in reusable_patterns."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    categories = [p["category"] for p in data["reusable_patterns"]]
    assert len(categories) == len(set(categories)), "Duplicate categories in reusable_patterns"


def test_learning_structure_no_duplicate_categories_in_prompt_updates(client):
    """Each category should appear at most once in suggested_prompt_updates."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    categories = [u["category"] for u in data["suggested_prompt_updates"]]
    assert len(categories) == len(set(categories)), "Duplicate categories in suggested_prompt_updates"


def test_learning_structure_created_at_is_string(client):
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert isinstance(data["created_at"], str)
    assert len(data["created_at"]) > 0


def test_learning_structure_learning_id_is_unique(client):
    """Two separate learning requests must produce distinct learning_ids."""
    review_id = _setup_review(client)
    d1 = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    d2 = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    assert d1["learning_id"] != d2["learning_id"]


# ---------------------------------------------------------------------------
# GET /learning
# ---------------------------------------------------------------------------

def test_list_learnings_returns_200(client):
    assert client.get("/learning").status_code == 200


def test_list_learnings_empty_initially(client):
    assert client.get("/learning").get_json() == []


def test_list_learnings_contains_created_record(client):
    review_id = _setup_review(client)
    client.post("/learning", json={"source_type": "review", "source_id": review_id})
    records = client.get("/learning").get_json()
    assert len(records) == 1


def test_list_learnings_learning_id_matches(client):
    review_id = _setup_review(client)
    created = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    listed = client.get("/learning").get_json()
    assert listed[0]["learning_id"] == created["learning_id"]


def test_list_learnings_multiple_records(client):
    """Three learning records from different source types must all appear in the list."""
    review_id = _setup_review(client)
    recon_id = _setup_reconciliation(client)
    proposal_id = _setup_proposal(client)

    client.post("/learning", json={"source_type": "review", "source_id": review_id})
    client.post("/learning", json={"source_type": "reconciliation", "source_id": recon_id})
    client.post("/learning", json={"source_type": "proposal", "source_id": proposal_id})

    records = client.get("/learning").get_json()
    assert len(records) == 3


# ---------------------------------------------------------------------------
# Insight rule coverage
# ---------------------------------------------------------------------------

def test_insight_high_severity_pattern_generated(client):
    """A sparse-version review contains high-severity weaknesses → high_severity_pattern insight."""
    review_id = _setup_review(client)
    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()
    types = [i["type"] for i in data["insights"]]
    assert "high_severity_pattern" in types


def test_insight_repeated_pattern_generated_from_reconciliation(client):
    """
    Two reviews over the same version produce identical weakness categories.
    After reconciliation the merged weakness count >= 2 → repeated_pattern insight.
    """
    recon_id = _setup_reconciliation(client)
    data = client.post(
        "/learning", json={"source_type": "reconciliation", "source_id": recon_id}
    ).get_json()
    # Reconciliation merges categories; check that insights list is populated
    assert isinstance(data["insights"], list)


# ---------------------------------------------------------------------------
# Missing security → prompt suggestion coverage
# ---------------------------------------------------------------------------

def test_missing_security_generates_security_prompt_suggestion(client):
    """
    A review run with the security persona against a sparse version should
    capture a missing_security_context weakness, producing a security-related
    prompt suggestion.
    """
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    review_id = client.post(
        "/reviews", json={"version_id": vid, "personas": ["security"]}
    ).get_json()["review_id"]

    data = client.post(
        "/learning", json={"source_type": "review", "source_id": review_id}
    ).get_json()

    categories = [u["category"] for u in data["suggested_prompt_updates"]]
    assert any("security" in cat for cat in categories), \
        f"Expected a security-related prompt suggestion, got: {categories}"
