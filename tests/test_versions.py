"""Tests for POST /versions and GET /versions."""


def _make_project(client, name="Proj"):
    return client.post("/projects", json={"name": name}).get_json()["project_id"]


def _make_artifact(client, project_id):
    return client.post("/artifacts", json={
        "project_id": project_id,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    }).get_json()["artifact_id"]


# ---------------------------------------------------------------------------
# POST /versions — valid input
# ---------------------------------------------------------------------------

def test_create_version_returns_201(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert res.status_code == 201


def test_create_version_returns_version_id(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert "version_id" in res.get_json()


def test_create_version_snapshot_contains_artifact(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    snapshot = res.get_json()["artifact_snapshot"]
    assert any(a["artifact_id"] == aid for a in snapshot)


def test_create_version_snapshot_contains_multiple_artifacts(client):
    pid = _make_project(client)
    aid1 = _make_artifact(client, pid)
    aid2 = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid1, aid2]})
    assert len(res.get_json()["artifact_snapshot"]) == 2


def test_create_version_accepts_config(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={
        "project_id": pid,
        "artifact_ids": [aid],
        "config": {"label": "v1"},
    })
    assert res.get_json()["config"]["label"] == "v1"


# ---------------------------------------------------------------------------
# POST /versions — invalid input
# ---------------------------------------------------------------------------

def test_create_version_missing_project_id_returns_400(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"artifact_ids": [aid]})
    assert res.status_code == 400


def test_create_version_unknown_project_returns_400(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": "bad-id", "artifact_ids": [aid]})
    assert res.status_code == 400


def test_create_version_empty_artifact_ids_returns_400(client):
    pid = _make_project(client)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": []})
    assert res.status_code == 400


def test_create_version_unknown_artifact_id_returns_400(client):
    pid = _make_project(client)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": ["ghost-id"]})
    assert res.status_code == 400


def test_create_version_error_body_has_error_key(client):
    res = client.post("/versions", json={})
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# GET /versions — list
# ---------------------------------------------------------------------------

def test_list_versions_returns_200(client):
    assert client.get("/versions").status_code == 200


def test_list_versions_empty_initially(client):
    assert client.get("/versions").get_json() == []


def test_list_versions_contains_created_version(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert len(client.get("/versions").get_json()) == 1


# ---------------------------------------------------------------------------
# Traceability: version carries project_id
# ---------------------------------------------------------------------------

def test_version_traces_to_project(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert res.get_json()["project_id"] == pid
