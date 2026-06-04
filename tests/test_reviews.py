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


def test_create_review_status_is_complete(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["status"] == "complete"


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



# ---------------------------------------------------------------------------
# Sprint 2 — structured result
# ---------------------------------------------------------------------------

def test_create_review_result_has_summary(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "summary" in res.get_json()["result"]


def test_create_review_result_has_weaknesses(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "weaknesses" in res.get_json()["result"]


def test_create_review_result_has_explainability(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "explainability" in res.get_json()["result"]


def test_create_review_summary_has_required_keys(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    summary = res.get_json()["result"]["summary"]
    for key in ("overall_assessment", "key_findings", "recommended_focus"):
        assert key in summary, f"Missing summary key: {key}"


def test_create_review_explainability_has_required_keys(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    explainability = res.get_json()["result"]["explainability"]
    assert "based_on" in explainability
    assert "rules_used" in explainability


def test_create_review_explainability_based_on_is_populated(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    based_on = res.get_json()["result"]["explainability"]["based_on"]
    assert "version_summary" in based_on


def test_create_review_weaknesses_are_list(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert isinstance(res.get_json()["result"]["weaknesses"], list)


def test_create_review_weakness_has_required_keys(client):
    """A generic artifact produces weaknesses — validate their structure."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    weaknesses = res.get_json()["result"]["weaknesses"]
    assert len(weaknesses) > 0, "Expected at least one weakness for a generic document artifact"
    for w in weaknesses:
        for key in ("weakness_id", "category", "severity", "description", "source_refs"):
            assert key in w, f"Missing weakness key: {key}"


def test_create_review_weakness_severity_is_valid(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    for w in res.get_json()["result"]["weaknesses"]:
        assert w["severity"] in ("low", "medium", "high")


def test_create_review_overall_assessment_is_string(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert isinstance(res.get_json()["result"]["summary"]["overall_assessment"], str)


def test_create_review_overall_assessment_is_not_empty(client):
    """overall_assessment must always contain a non-empty string."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["result"]["summary"]["overall_assessment"] != ""



# ---------------------------------------------------------------------------
# Sprint 3 — Persona and Prompt Foundation
# ---------------------------------------------------------------------------

def test_review_accepts_personas(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "personas": ["Architect"]})
    assert res.status_code == 201


def test_review_without_personas_still_works(client):
    """Backward compatibility: version_id-only payload must succeed."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.status_code == 201
    assert res.get_json()["status"] == "complete"


def test_personas_default_to_empty_list(client):
    """When no personas supplied, result.personas must be an empty list."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert res.get_json()["result"]["personas"] == []


def test_prompt_context_created(client):
    """result.prompt_context must exist in the review response."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    assert "prompt_context" in res.get_json()["result"]


def test_prompt_context_has_required_keys(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "personas": ["Architect"]})
    pc = res.get_json()["result"]["prompt_context"]
    for key in ("base_prompt", "persona_prompts", "user_context", "version_context_refs"):
        assert key in pc, f"Missing prompt_context key: {key}"


def test_prompt_context_version_context_refs_has_expected_values(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid})
    refs = res.get_json()["result"]["prompt_context"]["version_context_refs"]
    assert "version_summary" in refs
    assert "artifact_snapshot" in refs


def test_personas_stored_in_result(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "personas": ["Architect", "Security"]})
    personas = res.get_json()["result"]["personas"]
    assert "architect" in personas
    assert "security" in personas


def test_unknown_personas_are_dropped(client):
    """Unrecognised persona strings must not appear in stored personas."""
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "personas": ["Ghost"]})
    assert res.status_code == 201
    assert res.get_json()["result"]["personas"] == []


def test_user_context_stored_in_prompt_context(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={
        "version_id": vid,
        "user_context": "Focus on cloud deployment risks.",
    })
    uc = res.get_json()["result"]["prompt_context"]["user_context"]
    assert uc == "Focus on cloud deployment risks."


def test_architect_persona_produces_persona_prompt(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={"version_id": vid, "personas": ["Architect"]})
    pp = res.get_json()["result"]["prompt_context"]["persona_prompts"]
    assert len(pp) == 1
    assert pp[0]["persona"] == "Architect"


def test_review_accepts_all_three_personas(client):
    pid = _make_project(client)
    aid = _make_artifact(client, pid)
    vid = _make_version(client, pid, aid)
    res = client.post("/reviews", json={
        "version_id": vid,
        "personas": ["Architect", "Delivery Lead", "Security"],
    })
    assert res.status_code == 201
    personas = res.get_json()["result"]["personas"]
    assert set(personas) == {"architect", "delivery lead", "security"}
