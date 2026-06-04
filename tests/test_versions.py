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
# Cross-project artifact ownership validation
# ---------------------------------------------------------------------------

def test_create_version_same_project_artifacts_succeeds(client):
    """Artifacts that belong to the same project must be accepted."""
    pid = _make_project(client)
    aid1 = _make_artifact(client, pid)
    aid2 = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid1, aid2]})
    assert res.status_code == 201


def test_create_version_cross_project_artifact_returns_400(client):
    """An artifact from a different project must be rejected with 400."""
    pid_a = _make_project(client, name="ProjectA")
    pid_b = _make_project(client, name="ProjectB")
    aid_b = _make_artifact(client, pid_b)   # artifact belongs to project B
    res = client.post("/versions", json={"project_id": pid_a, "artifact_ids": [aid_b]})
    assert res.status_code == 400


def test_create_version_cross_project_error_message(client):
    """Error response must contain the 'error' key when cross-project artifact is used."""
    pid_a = _make_project(client, name="ProjectA")
    pid_b = _make_project(client, name="ProjectB")
    aid_b = _make_artifact(client, pid_b)
    res = client.post("/versions", json={"project_id": pid_a, "artifact_ids": [aid_b]})
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# Sprint 1 — version_summary field
# ---------------------------------------------------------------------------

def test_create_version_has_version_summary(client):
    """version_summary key must be present in every version response."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert "version_summary" in res.get_json()


def test_version_summary_has_all_required_keys(client):
    """version_summary must contain all nine defined keys."""
    from services.version_summary_service import SUMMARY_FIELDS
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    summary = res.get_json()["version_summary"]
    for key in SUMMARY_FIELDS:
        assert key in summary, f"Missing summary key: {key}"


def test_version_summary_list_fields_are_lists(client):
    """constraints, dependencies, and missing_information must be lists."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    summary = res.get_json()["version_summary"]
    for key in ("constraints", "dependencies", "missing_information"):
        assert isinstance(summary[key], list), f"Expected list for '{key}'"


def test_version_summary_stored_with_version(client):
    """version_summary returned by GET /versions must also contain all keys."""
    from services.version_summary_service import SUMMARY_FIELDS
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    versions = client.get("/versions").get_json()
    summary = versions[0]["version_summary"]
    for key in SUMMARY_FIELDS:
        assert key in summary


# ---------------------------------------------------------------------------
# Traceability: version carries project_id
# ---------------------------------------------------------------------------

def test_version_traces_to_project(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    res = client.post("/versions", json={"project_id": pid, "artifact_ids": [aid]})
    assert res.get_json()["project_id"] == pid
