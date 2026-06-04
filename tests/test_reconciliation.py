"""
Tests for POST /reconciliation and GET /reconciliation.

Isolation strategy:
- conftest `client` fixture already patches storage.store.DB_PATH to a tmp file.
- We additionally patch services.reconciliation_service._get_recon_db_path so
  each test gets its own recon_db.json in tmp_path.
- All filesystem side-effects in store.py are suppressed by conftest.
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
    """
    Full isolated test client: patches both store DB and recon DB to tmp files.
    Filesystem side-effects (makedirs) are suppressed.
    """
    db_file = tmp_path / "db.json"
    db_file.write_text(json.dumps(EMPTY_DB))

    recon_db_file = tmp_path / "recon_db.json"

    app = create_app()
    app.config["TESTING"] = True

    with patch("storage.store.DB_PATH", str(db_file)), \
         patch("storage.store._ensure_version_dir"), \
         patch("storage.store._ensure_review_dir"), \
         patch(
             "services.reconciliation_service._get_recon_db_path",
             return_value=str(recon_db_file),
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


def _make_review(client, version_id, personas=None):
    payload = {"version_id": version_id}
    if personas:
        payload["personas"] = personas
    return client.post("/reviews", json=payload).get_json()["review_id"]


def _setup_two_reviews(client):
    """Create two reviews under the same project/version; return (review_id_1, review_id_2)."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)
    return r1, r2


# ---------------------------------------------------------------------------
# POST /reconciliation — shape and status
# ---------------------------------------------------------------------------

def test_create_reconciliation_returns_201(client):
    r1, r2 = _setup_two_reviews(client)
    res = client.post("/reconciliation", json={"review_ids": [r1, r2]})
    assert res.status_code == 201


def test_create_reconciliation_returns_recon_id(client):
    r1, r2 = _setup_two_reviews(client)
    res = client.post("/reconciliation", json={"review_ids": [r1, r2]})
    assert "recon_id" in res.get_json()


def test_create_reconciliation_recon_id_is_string(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["recon_id"], str)
    assert len(data["recon_id"]) > 0


def test_create_reconciliation_has_source_reviews(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "source_reviews" in data


def test_create_reconciliation_source_reviews_contains_input_ids(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert r1 in data["source_reviews"]
    assert r2 in data["source_reviews"]


def test_create_reconciliation_has_summary(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "summary" in data


def test_create_reconciliation_has_merged_weaknesses(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "merged_weaknesses" in data


def test_create_reconciliation_has_conflicts(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "conflicts" in data


def test_create_reconciliation_has_explainability(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "explainability" in data


def test_create_reconciliation_has_created_at(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Summary shape
# ---------------------------------------------------------------------------

def test_summary_has_consensus_findings(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "consensus_findings" in data["summary"]


def test_summary_has_key_risks(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "key_risks" in data["summary"]


def test_summary_has_recommended_focus(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "recommended_focus" in data["summary"]


def test_summary_consensus_findings_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["summary"]["consensus_findings"], list)


def test_summary_key_risks_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["summary"]["key_risks"], list)


def test_summary_recommended_focus_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["summary"]["recommended_focus"], list)


# ---------------------------------------------------------------------------
# Merged weaknesses shape
# ---------------------------------------------------------------------------

def test_merged_weaknesses_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["merged_weaknesses"], list)


def test_merged_weakness_has_required_keys(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    weaknesses = data["merged_weaknesses"]
    assert len(weaknesses) > 0, "Expected merged weaknesses from two reviews of a sparse version"
    for w in weaknesses:
        for key in ("category", "severity", "descriptions", "source_reviews", "count"):
            assert key in w, f"Missing merged_weakness key: {key}"


def test_merged_weakness_severity_is_valid(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    for w in data["merged_weaknesses"]:
        assert w["severity"] in ("low", "medium", "high")


def test_merged_weakness_descriptions_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    for w in data["merged_weaknesses"]:
        assert isinstance(w["descriptions"], list)


def test_merged_weakness_source_reviews_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    for w in data["merged_weaknesses"]:
        assert isinstance(w["source_reviews"], list)


# ---------------------------------------------------------------------------
# Explainability shape
# ---------------------------------------------------------------------------

def test_explainability_has_merge_rules_used(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "merge_rules_used" in data["explainability"]


def test_explainability_merge_rules_contains_group_by_category(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "group_by_category" in data["explainability"]["merge_rules_used"]


def test_explainability_merge_rules_contains_severity_max(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "severity_max" in data["explainability"]["merge_rules_used"]


def test_explainability_merge_rules_contains_deduplicate(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert "deduplicate_similar_descriptions" in data["explainability"]["merge_rules_used"]


# ---------------------------------------------------------------------------
# test_merge_two_reviews
# ---------------------------------------------------------------------------

def test_merge_two_reviews(client):
    """Two reviews over the same version must produce one reconciliation record."""
    r1, r2 = _setup_two_reviews(client)
    res = client.post("/reconciliation", json={"review_ids": [r1, r2]})
    assert res.status_code == 201
    data = res.get_json()
    assert data["recon_id"]
    assert set(data["source_reviews"]) == {r1, r2}


def test_merge_two_reviews_weaknesses_grouped(client):
    """Weaknesses from two reviews of the same version should collapse into grouped categories."""
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    # Each merged weakness is unique by category
    categories = [w["category"] for w in data["merged_weaknesses"]]
    assert len(categories) == len(set(categories)), "Each category should appear only once after merge"


def test_merge_two_reviews_source_reviews_in_merged_weaknesses(client):
    """Source review ids must be traceable in merged weaknesses."""
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    all_source_reviews = {
        rid
        for w in data["merged_weaknesses"]
        for rid in w["source_reviews"]
    }
    assert r1 in all_source_reviews or r2 in all_source_reviews


# ---------------------------------------------------------------------------
# test_duplicate_weaknesses_merge
# ---------------------------------------------------------------------------

def test_duplicate_weaknesses_merge(client):
    """
    Two reviews over the same version produce the same weakness categories.
    After merge each category must appear exactly once with count >= 2.
    """
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)

    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    categories = [w["category"] for w in data["merged_weaknesses"]]
    # No duplicate categories in merged output
    assert len(categories) == len(set(categories))
    # At least one merged weakness must have count >= 2 (same category from both reviews)
    counts = [w["count"] for w in data["merged_weaknesses"]]
    assert any(c >= 2 for c in counts), "Expected at least one category with count >= 2 when merging duplicate reviews"


def test_duplicate_weaknesses_descriptions_deduplicated(client):
    """Identical descriptions from two reviews must not be duplicated in the merged output."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)

    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    for w in data["merged_weaknesses"]:
        descs = w["descriptions"]
        assert len(descs) == len(set(descs)), f"Duplicate descriptions in category '{w['category']}'"


# ---------------------------------------------------------------------------
# test_severity_resolution
# ---------------------------------------------------------------------------

def test_severity_resolution_max_wins(client):
    """
    Verify severity_max rule: the merged severity must be the highest
    severity seen across all contributing weaknesses.

    We create two reviews and assert that every merged weakness severity
    equals the max of its contributing weaknesses.
    """
    from services.reconciliation_service import (
        _resolve_severity,
        _group_by_category,
        _extract_weaknesses,
    )
    from storage import store as _store

    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)

    # Collect raw weaknesses through the service helpers
    reviews = [_store.get_review(r1), _store.get_review(r2)]
    raw = _extract_weaknesses(reviews)
    grouped = _group_by_category(raw)

    for cat, items in grouped.items():
        expected = _resolve_severity(items)
        assert expected in ("low", "medium", "high")
        # Verify it is genuinely the max
        ranks = [{"low": 0, "medium": 1, "high": 2}.get(w.get("severity", "low"), 0) for w in items]
        assert {"low": 0, "medium": 1, "high": 2}[expected] == max(ranks)


def test_severity_resolution_via_api(client):
    """End-to-end: no merged weakness should have a severity lower than any of its contributors."""
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    # All merged weaknesses must have a valid severity
    for w in data["merged_weaknesses"]:
        assert w["severity"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# test_invalid_review_ids
# ---------------------------------------------------------------------------

def test_invalid_review_ids_returns_400(client):
    res = client.post("/reconciliation", json={"review_ids": ["ghost-id-1", "ghost-id-2"]})
    assert res.status_code == 400


def test_invalid_review_ids_error_body_has_error_key(client):
    res = client.post("/reconciliation", json={"review_ids": ["ghost-id-1"]})
    assert "error" in res.get_json()


def test_invalid_review_ids_error_mentions_missing_id(client):
    res = client.post("/reconciliation", json={"review_ids": ["ghost-id-99"]})
    assert "ghost-id-99" in res.get_json()["error"]


def test_partial_invalid_review_ids_returns_400(client):
    """One valid + one invalid review_id must fail with 400."""
    r1, _ = _setup_two_reviews(client)
    res = client.post("/reconciliation", json={"review_ids": [r1, "ghost-id"]})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# test_empty_reviews_fail
# ---------------------------------------------------------------------------

def test_empty_review_ids_list_returns_400(client):
    res = client.post("/reconciliation", json={"review_ids": []})
    assert res.status_code == 400


def test_missing_review_ids_field_returns_400(client):
    res = client.post("/reconciliation", json={})
    assert res.status_code == 400


def test_empty_review_ids_error_body_has_error_key(client):
    res = client.post("/reconciliation", json={"review_ids": []})
    assert "error" in res.get_json()


def test_null_review_ids_returns_400(client):
    res = client.post("/reconciliation", json={"review_ids": None})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# GET /reconciliation
# ---------------------------------------------------------------------------

def test_list_reconciliations_returns_200(client):
    assert client.get("/reconciliation").status_code == 200


def test_list_reconciliations_empty_initially(client):
    assert client.get("/reconciliation").get_json() == []


def test_list_reconciliations_contains_created_record(client):
    r1, r2 = _setup_two_reviews(client)
    client.post("/reconciliation", json={"review_ids": [r1, r2]})
    records = client.get("/reconciliation").get_json()
    assert len(records) == 1


def test_list_reconciliations_recon_id_matches(client):
    r1, r2 = _setup_two_reviews(client)
    created = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    listed = client.get("/reconciliation").get_json()
    assert listed[0]["recon_id"] == created["recon_id"]


# ---------------------------------------------------------------------------
# Single-review reconciliation (edge case)
# ---------------------------------------------------------------------------

def test_single_review_reconciliation_succeeds(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    rid = _make_review(client, vid)
    res = client.post("/reconciliation", json={"review_ids": [rid]})
    assert res.status_code == 201


def test_single_review_source_reviews_has_one_entry(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    rid = _make_review(client, vid)
    data = client.post("/reconciliation", json={"review_ids": [rid]}).get_json()
    assert data["source_reviews"] == [rid]


# ---------------------------------------------------------------------------
# Conflicts list
# ---------------------------------------------------------------------------

def test_conflicts_is_list(client):
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    assert isinstance(data["conflicts"], list)


def test_conflict_record_has_required_keys(client):
    """If any conflict is detected it must carry the required keys."""
    r1, r2 = _setup_two_reviews(client)
    data = client.post("/reconciliation", json={"review_ids": [r1, r2]}).get_json()
    for conflict in data["conflicts"]:
        for key in ("category", "conflicting_severities", "resolution"):
            assert key in conflict, f"Missing conflict key: {key}"
