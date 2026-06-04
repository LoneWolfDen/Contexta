"""
Tests for POST /proposal and GET /proposal.

Isolation strategy:
- conftest `client` fixture patches storage.store.DB_PATH to a tmp file.
- We additionally patch:
    - services.reconciliation_service._get_recon_db_path → tmp recon_db.json
    - services.proposal_service._get_proposal_db_path  → tmp proposal_db.json
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
         ):
        with app.test_client() as c:
            yield c


# ---------------------------------------------------------------------------
# Helpers — build full chain
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


def _make_reconciliation(client, review_ids):
    return client.post("/reconciliation", json={"review_ids": review_ids}).get_json()["recon_id"]


def _setup_review(client):
    """Create project → artifact → version → review; return review_id."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    return _make_review(client, vid)


def _setup_reconciliation(client):
    """Create two reviews and reconcile them; return recon_id."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)
    return _make_reconciliation(client, [r1, r2])


# ---------------------------------------------------------------------------
# test_generate_proposal_from_review
# ---------------------------------------------------------------------------

def test_generate_proposal_from_review_returns_201(client):
    review_id = _setup_review(client)
    res = client.post("/proposal", json={"review_id": review_id})
    assert res.status_code == 201


def test_generate_proposal_from_review_returns_proposal_id(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert "proposal_id" in data
    assert isinstance(data["proposal_id"], str)
    assert len(data["proposal_id"]) > 0


def test_generate_proposal_from_review_source_type_is_review(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert data["source_type"] == "review"


def test_generate_proposal_from_review_source_id_matches(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert data["source_id"] == review_id


def test_generate_proposal_from_review_has_all_required_top_level_keys(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for key in ("proposal_id", "source_type", "source_id", "source_refs",
                "summary", "recommendations", "delivery_considerations",
                "kpis", "references", "created_at"):
        assert key in data, f"Missing top-level key: {key}"


def test_generate_proposal_from_review_summary_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for key in ("executive_summary", "problem_statement", "recommended_solution"):
        assert key in data["summary"], f"Missing summary key: {key}"


def test_generate_proposal_from_review_summary_values_are_strings(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for key in ("executive_summary", "problem_statement", "recommended_solution"):
        assert isinstance(data["summary"][key], str)
        assert len(data["summary"][key]) > 0


def test_generate_proposal_from_review_has_created_at(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert "created_at" in data
    assert isinstance(data["created_at"], str)


# ---------------------------------------------------------------------------
# test_generate_proposal_from_reconciliation
# ---------------------------------------------------------------------------

def test_generate_proposal_from_reconciliation_returns_201(client):
    recon_id = _setup_reconciliation(client)
    res = client.post("/proposal", json={"recon_id": recon_id})
    assert res.status_code == 201


def test_generate_proposal_from_reconciliation_returns_proposal_id(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert "proposal_id" in data
    assert len(data["proposal_id"]) > 0


def test_generate_proposal_from_reconciliation_source_type_is_reconciliation(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert data["source_type"] == "reconciliation"


def test_generate_proposal_from_reconciliation_source_id_matches(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert data["source_id"] == recon_id


def test_generate_proposal_from_reconciliation_has_all_required_top_level_keys(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    for key in ("proposal_id", "source_type", "source_id", "source_refs",
                "summary", "recommendations", "delivery_considerations",
                "kpis", "references", "created_at"):
        assert key in data, f"Missing top-level key: {key}"


def test_generate_proposal_from_reconciliation_summary_has_required_keys(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    for key in ("executive_summary", "problem_statement", "recommended_solution"):
        assert key in data["summary"], f"Missing summary key: {key}"


def test_generate_proposal_from_reconciliation_source_refs_contains_review_ids(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)
    recon_id = _make_reconciliation(client, [r1, r2])
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert r1 in data["source_refs"] or r2 in data["source_refs"]


# ---------------------------------------------------------------------------
# test_empty_input_fails
# ---------------------------------------------------------------------------

def test_empty_body_returns_400(client):
    res = client.post("/proposal", json={})
    assert res.status_code == 400


def test_empty_body_error_has_error_key(client):
    res = client.post("/proposal", json={})
    assert "error" in res.get_json()


def test_no_json_body_returns_400(client):
    res = client.post("/proposal")
    assert res.status_code == 400


def test_both_ids_provided_returns_400(client):
    review_id = _setup_review(client)
    recon_id = _setup_reconciliation(client)
    res = client.post("/proposal", json={"review_id": review_id, "recon_id": recon_id})
    assert res.status_code == 400


def test_both_ids_error_has_error_key(client):
    review_id = _setup_review(client)
    recon_id = _setup_reconciliation(client)
    res = client.post("/proposal", json={"review_id": review_id, "recon_id": recon_id})
    assert "error" in res.get_json()


def test_unknown_review_id_returns_400(client):
    res = client.post("/proposal", json={"review_id": "ghost-review-id"})
    assert res.status_code == 400


def test_unknown_review_id_error_mentions_id(client):
    res = client.post("/proposal", json={"review_id": "ghost-review-id"})
    assert "ghost-review-id" in res.get_json()["error"]


def test_unknown_recon_id_returns_400(client):
    res = client.post("/proposal", json={"recon_id": "ghost-recon-id"})
    assert res.status_code == 400


def test_unknown_recon_id_error_mentions_id(client):
    res = client.post("/proposal", json={"recon_id": "ghost-recon-id"})
    assert "ghost-recon-id" in res.get_json()["error"]


# ---------------------------------------------------------------------------
# test_recommendations_created
# ---------------------------------------------------------------------------

def test_recommendations_is_list(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert isinstance(data["recommendations"], list)


def test_recommendations_not_empty_for_review_with_weaknesses(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert len(data["recommendations"]) > 0


def test_recommendation_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for rec in data["recommendations"]:
        for key in ("category", "recommendation", "priority"):
            assert key in rec, f"Missing recommendation key: {key}"


def test_recommendation_priority_is_valid(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for rec in data["recommendations"]:
        assert rec["priority"] in ("high", "medium", "low"), \
            f"Invalid priority: {rec['priority']}"


def test_recommendation_text_is_non_empty_string(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for rec in data["recommendations"]:
        assert isinstance(rec["recommendation"], str)
        assert len(rec["recommendation"]) > 0


def test_recommendations_sorted_high_before_low(client):
    """High-priority recommendations must appear before low-priority ones."""
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    recs = data["recommendations"]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    priorities = [priority_order[r["priority"]] for r in recs]
    assert priorities == sorted(priorities), "Recommendations are not sorted high → medium → low"


def test_recommendations_no_duplicate_categories(client):
    """Each category should appear at most once in the recommendations list."""
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    categories = [r["category"].lower().strip() for r in data["recommendations"]]
    assert len(categories) == len(set(categories)), "Duplicate categories in recommendations"


def test_recommendations_from_reconciliation_not_empty(client):
    recon_id = _setup_reconciliation(client)
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert len(data["recommendations"]) > 0


# ---------------------------------------------------------------------------
# Output shape — delivery_considerations, kpis, references
# ---------------------------------------------------------------------------

def test_delivery_considerations_is_list(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert isinstance(data["delivery_considerations"], list)


def test_delivery_considerations_not_empty(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert len(data["delivery_considerations"]) > 0


def test_delivery_considerations_are_strings(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for item in data["delivery_considerations"]:
        assert isinstance(item, str) and len(item) > 0


def test_kpis_is_list(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert isinstance(data["kpis"], list)


def test_kpis_not_empty(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert len(data["kpis"]) > 0


def test_kpis_are_strings(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for item in data["kpis"]:
        assert isinstance(item, str) and len(item) > 0


def test_references_is_list(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert isinstance(data["references"], list)


def test_references_not_empty(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert len(data["references"]) > 0


def test_reference_has_required_keys(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    for ref in data["references"]:
        for key in ("type", "id", "note"):
            assert key in ref, f"Missing reference key: {key}"


def test_reference_contains_source_id(client):
    review_id = _setup_review(client)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    ref_ids = [r["id"] for r in data["references"]]
    assert review_id in ref_ids


# ---------------------------------------------------------------------------
# GET /proposal
# ---------------------------------------------------------------------------

def test_list_proposals_returns_200(client):
    assert client.get("/proposal").status_code == 200


def test_list_proposals_empty_initially(client):
    assert client.get("/proposal").get_json() == []


def test_list_proposals_contains_created_record(client):
    review_id = _setup_review(client)
    client.post("/proposal", json={"review_id": review_id})
    records = client.get("/proposal").get_json()
    assert len(records) == 1


def test_list_proposals_proposal_id_matches(client):
    review_id = _setup_review(client)
    created = client.post("/proposal", json={"review_id": review_id}).get_json()
    listed = client.get("/proposal").get_json()
    assert listed[0]["proposal_id"] == created["proposal_id"]


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------

def test_proposal_from_review_traceability(client):
    """Proposal source_id must trace back to the originating review."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    review_id = _make_review(client, vid)
    data = client.post("/proposal", json={"review_id": review_id}).get_json()
    assert data["source_id"] == review_id
    assert data["source_type"] == "review"


def test_proposal_from_reconciliation_traceability(client):
    """Proposal source_id must trace back to the originating reconciliation."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    r1 = _make_review(client, vid)
    r2 = _make_review(client, vid)
    recon_id = _make_reconciliation(client, [r1, r2])
    data = client.post("/proposal", json={"recon_id": recon_id}).get_json()
    assert data["source_id"] == recon_id
    assert data["source_type"] == "reconciliation"


def test_proposal_is_deterministic(client):
    """Same review_id must produce structurally identical proposal output."""
    review_id = _setup_review(client)
    d1 = client.post("/proposal", json={"review_id": review_id}).get_json()
    d2 = client.post("/proposal", json={"review_id": review_id}).get_json()
    # proposal_id and created_at will differ (new record each time), but
    # the structural content must be identical
    for key in ("summary", "recommendations", "delivery_considerations", "kpis"):
        assert d1[key] == d2[key], f"Non-deterministic output for key: {key}"
