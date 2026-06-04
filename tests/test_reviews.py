"""Tests for POST /reviews and GET /reviews."""


def _make_project(client, name="Proj"):
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


# ---------------------------------------------------------------------------
# POST /reviews — valid input
# ---------------------------------------------------------------------------

def test_create_review_returns_201(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.status_code == 201


def test_create_review_returns_review_id(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "review_id" in res.get_json()


def test_create_review_is_mock_status(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["status"] == "mock"


def test_create_review_has_result_field(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "result" in res.get_json()


def test_create_review_accepts_config(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "config": {"mode": "quick"}})
    assert res.get_json()["config"]["mode"] == "quick"


# ---------------------------------------------------------------------------
# POST /reviews — invalid input
# ---------------------------------------------------------------------------

def test_create_review_missing_version_id_returns_400(client):
    res = client.post("/reviews", json={})
    assert res.status_code == 400


def test_create_review_unknown_version_id_returns_400(client):
    res = client.post("/reviews", json={"version_id": "ghost-id"})
    assert res.status_code == 400


def test_create_review_error_body_has_error_key(client):
    res = client.post("/reviews", json={})
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# GET /reviews — list
# ---------------------------------------------------------------------------

def test_list_reviews_returns_200(client):
    assert client.get("/reviews").status_code == 200


def test_list_reviews_empty_initially(client):
    assert client.get("/reviews").get_json() == []


def test_list_reviews_contains_created_review(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    client.post("/reviews", json={"version_id": vid})
    assert len(client.get("/reviews").get_json()) == 1


# ---------------------------------------------------------------------------
# Traceability: review → version → project
# ---------------------------------------------------------------------------

def test_review_traces_to_version(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["version_id"] == vid


def test_review_traces_to_project(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["project_id"] == pid


def test_full_traceability_chain(client):
    """End-to-end: Project → Artifact → Version → Review all linked."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    review = client.post("/reviews", json={"version_id": vid}).get_json()

    assert review["project_id"] == pid
    assert review["version_id"] == vid

    version = client.get("/versions").get_json()[0]
    assert version["project_id"] == pid
    snapshot_ids = [a["artifact_id"] for a in version["artifact_snapshot"]]
    assert aid in snapshot_ids
