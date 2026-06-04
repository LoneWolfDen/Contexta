"""Tests for POST /projects and GET /projects."""


# ---------------------------------------------------------------------------
# POST /projects — valid input
# ---------------------------------------------------------------------------

def test_create_project_returns_201(client):
    res = client.post("/projects", json={"name": "Alpha"})
    assert res.status_code == 201


def test_create_project_returns_project_id(client):
    res = client.post("/projects", json={"name": "Alpha"})
    data = res.get_json()
    assert "project_id" in data


def test_create_project_persists_name(client):
    res = client.post("/projects", json={"name": "Alpha"})
    data = res.get_json()
    assert data["name"] == "Alpha"


def test_create_project_accepts_config(client):
    res = client.post("/projects", json={"name": "Beta", "config": {"region": "us-east"}})
    data = res.get_json()
    assert data["config"]["region"] == "us-east"


def test_create_project_empty_config_by_default(client):
    res = client.post("/projects", json={"name": "Gamma"})
    data = res.get_json()
    assert data["config"] == {}


# ---------------------------------------------------------------------------
# POST /projects — invalid input
# ---------------------------------------------------------------------------

def test_create_project_missing_name_returns_400(client):
    res = client.post("/projects", json={})
    assert res.status_code == 400


def test_create_project_blank_name_returns_400(client):
    res = client.post("/projects", json={"name": "   "})
    assert res.status_code == 400


def test_create_project_error_body_contains_error_key(client):
    res = client.post("/projects", json={})
    data = res.get_json()
    assert "error" in data


# ---------------------------------------------------------------------------
# GET /projects — list
# ---------------------------------------------------------------------------

def test_list_projects_returns_200(client):
    res = client.get("/projects")
    assert res.status_code == 200


def test_list_projects_empty_initially(client):
    res = client.get("/projects")
    assert res.get_json() == []


def test_list_projects_contains_created_project(client):
    client.post("/projects", json={"name": "Delta"})
    res = client.get("/projects")
    names = [p["name"] for p in res.get_json()]
    assert "Delta" in names


def test_list_projects_returns_all_projects(client):
    client.post("/projects", json={"name": "P1"})
    client.post("/projects", json={"name": "P2"})
    res = client.get("/projects")
    assert len(res.get_json()) == 2
