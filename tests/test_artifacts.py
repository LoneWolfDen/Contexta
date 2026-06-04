"""Tests for POST /artifacts and GET /artifacts."""


def _make_project(client, name="Proj"):
    res = client.post("/projects", json={"name": name})
    return res.get_json()["project_id"]


# ---------------------------------------------------------------------------
# POST /artifacts — valid input
# ---------------------------------------------------------------------------

def test_create_artifact_returns_201(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.status_code == 201


def test_create_artifact_returns_artifact_id(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert "artifact_id" in res.get_json()


def test_create_artifact_stores_all_fields(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "diagram",
        "source_type": "url",
        "file_path": "/files/arch.xml",
        "included_in_review": False,
    })
    data = res.get_json()
    assert data["project_id"] == pid
    assert data["type"] == "diagram"
    assert data["source_type"] == "url"
    assert data["file_path"] == "/files/arch.xml"
    assert data["included_in_review"] is False


def test_create_artifact_included_in_review_defaults_true(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.get_json()["included_in_review"] is True


def test_create_artifact_accepts_config(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
        "config": {"lang": "en"},
    })
    assert res.get_json()["config"]["lang"] == "en"


# ---------------------------------------------------------------------------
# POST /artifacts — invalid input
# ---------------------------------------------------------------------------

def test_create_artifact_missing_project_id_returns_400(client):
    res = client.post("/artifacts", json={
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.status_code == 400


def test_create_artifact_unknown_project_returns_400(client):
    res = client.post("/artifacts", json={
        "project_id": "does-not-exist",
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.status_code == 400


def test_create_artifact_missing_type_returns_400(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.status_code == 400


def test_create_artifact_missing_file_path_returns_400(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
    })
    assert res.status_code == 400


def test_create_artifact_error_body_has_error_key(client):
    res = client.post("/artifacts", json={})
    assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# GET /artifacts — list
# ---------------------------------------------------------------------------

def test_list_artifacts_returns_200(client):
    assert client.get("/artifacts").status_code == 200


def test_list_artifacts_empty_initially(client):
    assert client.get("/artifacts").get_json() == []


def test_list_artifacts_contains_created_artifact(client):
    pid = _make_project(client)
    client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    artifacts = client.get("/artifacts").get_json()
    assert len(artifacts) == 1


# ---------------------------------------------------------------------------
# Traceability: artifact carries project_id
# ---------------------------------------------------------------------------

def test_artifact_traces_to_project(client):
    pid = _make_project(client)
    res = client.post("/artifacts", json={
        "project_id": pid,
        "type": "document",
        "source_type": "upload",
        "file_path": "/files/doc.pdf",
    })
    assert res.get_json()["project_id"] == pid
