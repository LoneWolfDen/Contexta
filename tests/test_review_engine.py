"""
Unit tests for services/review_analysis_service.py

Tests call generate_review() directly — no Flask client needed.
Covers: output shape, weakness detection, empty/missing input safety, traceability.
"""

from services.review_analysis_service import generate_review

# ---------------------------------------------------------------------------
# Fixtures — reusable version dicts
# ---------------------------------------------------------------------------

def _make_version(summary_overrides=None, snapshot=None, version_id="v-001", project_id="p-001"):
    """Build a minimal version dict for testing."""
    base_summary = {
        "client_ask": "",
        "solution_understanding": "",
        "technology_landscape": "",
        "delivery_model": "",
        "tooling_recommendations": "",
        "constraints": [],
        "dependencies": [],
        "architecture_understanding": "",
        "missing_information": [],
    }
    if summary_overrides:
        base_summary.update(summary_overrides)
    return {
        "version_id": version_id,
        "project_id": project_id,
        "artifact_snapshot": snapshot or [],
        "version_summary": base_summary,
        "config": {},
    }


def _fully_covered_summary():
    """Return a version_summary with all required string fields populated."""
    return {
        "client_ask":              "Client brief: brief.pdf",
        "solution_understanding":  "Solution design: solution.pdf",
        "technology_landscape":    "Tech stack: stack.pdf",
        "delivery_model":          "Delivery plan: plan.pdf",
        "tooling_recommendations": "Tooling: tools.pdf",
        "constraints":             ["compliance: sla.pdf"],
        "dependencies":            ["integration: api.pdf"],
        "architecture_understanding": "Architecture: arch.drawio",
        "missing_information":     [],
    }


# ---------------------------------------------------------------------------
# Output shape — all top-level keys always present
# ---------------------------------------------------------------------------

def test_generate_review_returns_dict():
    result = generate_review(_make_version())
    assert isinstance(result, dict)


def test_result_has_summary_key():
    result = generate_review(_make_version())
    assert "summary" in result


def test_result_has_weaknesses_key():
    result = generate_review(_make_version())
    assert "weaknesses" in result


def test_result_has_explainability_key():
    result = generate_review(_make_version())
    assert "explainability" in result


def test_summary_has_overall_assessment():
    result = generate_review(_make_version())
    assert "overall_assessment" in result["summary"]


def test_summary_has_key_findings():
    result = generate_review(_make_version())
    assert "key_findings" in result["summary"]


def test_summary_has_recommended_focus():
    result = generate_review(_make_version())
    assert "recommended_focus" in result["summary"]


def test_explainability_has_based_on():
    result = generate_review(_make_version())
    assert "based_on" in result["explainability"]


def test_explainability_has_rules_used():
    result = generate_review(_make_version())
    assert "rules_used" in result["explainability"]


def test_weaknesses_is_list():
    result = generate_review(_make_version())
    assert isinstance(result["weaknesses"], list)


def test_key_findings_is_list():
    result = generate_review(_make_version())
    assert isinstance(result["summary"]["key_findings"], list)


def test_recommended_focus_is_list():
    result = generate_review(_make_version())
    assert isinstance(result["summary"]["recommended_focus"], list)


def test_based_on_is_list():
    result = generate_review(_make_version())
    assert isinstance(result["explainability"]["based_on"], list)


def test_rules_used_is_list():
    result = generate_review(_make_version())
    assert isinstance(result["explainability"]["rules_used"], list)


# ---------------------------------------------------------------------------
# test_no_crash_with_empty_summary
# ---------------------------------------------------------------------------

def test_empty_version_summary_does_not_raise():
    version = _make_version(summary_overrides={}, snapshot=[])
    result = generate_review(version)
    assert isinstance(result, dict)


def test_missing_version_summary_key_does_not_raise():
    """version dict without version_summary key must not crash."""
    version = {"version_id": "v-x", "project_id": "p-x", "artifact_snapshot": []}
    result = generate_review(version)
    assert isinstance(result, dict)


def test_missing_artifact_snapshot_key_does_not_raise():
    """version dict without artifact_snapshot key must not crash."""
    version = {"version_id": "v-x", "project_id": "p-x", "version_summary": {}}
    result = generate_review(version)
    assert isinstance(result, dict)


def test_none_version_summary_does_not_raise():
    version = _make_version()
    version["version_summary"] = None
    result = generate_review(version)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# test_weakness_detected — empty summary fields → weaknesses generated
# ---------------------------------------------------------------------------

def test_empty_summary_produces_weaknesses():
    result = generate_review(_make_version())
    assert len(result["weaknesses"]) > 0


def test_weakness_has_weakness_id():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert "weakness_id" in w


def test_weakness_has_category():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert "category" in w


def test_weakness_has_severity():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert "severity" in w


def test_weakness_has_description():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert "description" in w
        assert isinstance(w["description"], str)
        assert w["description"] != ""


def test_weakness_has_source_refs():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert "source_refs" in w
        assert isinstance(w["source_refs"], list)


def test_weakness_severity_valid_values():
    result = generate_review(_make_version())
    for w in result["weaknesses"]:
        assert w["severity"] in ("low", "medium", "high")


def test_missing_client_ask_produces_high_severity_weakness():
    result = generate_review(_make_version(summary_overrides={"client_ask": ""}))
    severities = {w["severity"] for w in result["weaknesses"]}
    assert "high" in severities


def test_missing_solution_understanding_produces_high_weakness():
    result = generate_review(_make_version(summary_overrides={"solution_understanding": ""}))
    severities = {w["severity"] for w in result["weaknesses"]}
    assert "high" in severities


def test_missing_architecture_produces_high_weakness():
    result = generate_review(_make_version(summary_overrides={"architecture_understanding": ""}))
    severities = {w["severity"] for w in result["weaknesses"]}
    assert "high" in severities


def test_empty_summary_overall_assessment_mentions_high():
    """When high-severity gaps exist the assessment must reference them."""
    result = generate_review(_make_version())
    assessment = result["summary"]["overall_assessment"].lower()
    assert "high" in assessment or "critical" in assessment or "missing" in assessment


def test_limited_artifact_coverage_produces_weakness():
    """Single artifact triggers limited_coverage weakness."""
    snapshot = [{"artifact_id": "a1", "project_id": "p1", "type": "document",
                 "source_type": "upload", "file_path": "/files/doc.pdf",
                 "included_in_review": True, "config": {}}]
    result = generate_review(_make_version(snapshot=snapshot))
    categories = [w["category"] for w in result["weaknesses"]]
    assert "limited_coverage" in categories


def test_two_artifacts_no_coverage_weakness():
    """Two or more artifacts must not trigger limited_coverage weakness."""
    snapshot = [
        {"artifact_id": "a1", "project_id": "p1", "type": "document",
         "source_type": "upload", "file_path": "/files/doc1.pdf",
         "included_in_review": True, "config": {}},
        {"artifact_id": "a2", "project_id": "p1", "type": "document",
         "source_type": "upload", "file_path": "/files/doc2.pdf",
         "included_in_review": True, "config": {}},
    ]
    result = generate_review(_make_version(snapshot=snapshot))
    categories = [w["category"] for w in result["weaknesses"]]
    assert "limited_coverage" not in categories


def test_fully_covered_summary_produces_no_weaknesses():
    """A version with all summary fields populated and 2+ artifacts has no weaknesses."""
    snapshot = [
        {"artifact_id": "a1", "project_id": "p1", "type": "brief",
         "source_type": "upload", "file_path": "/files/brief.pdf",
         "included_in_review": True, "config": {}},
        {"artifact_id": "a2", "project_id": "p1", "type": "architecture",
         "source_type": "upload", "file_path": "/files/arch.drawio",
         "included_in_review": True, "config": {}},
    ]
    result = generate_review(_make_version(
        summary_overrides=_fully_covered_summary(),
        snapshot=snapshot,
    ))
    assert result["weaknesses"] == []


def test_fully_covered_summary_overall_assessment_positive():
    snapshot = [
        {"artifact_id": "a1", "project_id": "p1", "type": "brief",
         "source_type": "upload", "file_path": "/files/brief.pdf",
         "included_in_review": True, "config": {}},
        {"artifact_id": "a2", "project_id": "p1", "type": "architecture",
         "source_type": "upload", "file_path": "/files/arch.drawio",
         "included_in_review": True, "config": {}},
    ]
    result = generate_review(_make_version(
        summary_overrides=_fully_covered_summary(),
        snapshot=snapshot,
    ))
    assessment = result["summary"]["overall_assessment"].lower()
    assert "no weakness" in assessment or "covered" in assessment or "all" in assessment


# ---------------------------------------------------------------------------
# test_traceability — version_id flows through correctly
# ---------------------------------------------------------------------------

def test_generate_review_does_not_strip_version_id():
    """generate_review must not touch or drop version_id from the version dict."""
    version = _make_version(version_id="v-trace-123")
    generate_review(version)
    assert version["version_id"] == "v-trace-123"


def test_explainability_based_on_contains_version_summary():
    result = generate_review(_make_version())
    assert "version_summary" in result["explainability"]["based_on"]


def test_explainability_based_on_contains_artifact_snapshot():
    result = generate_review(_make_version())
    assert "artifact_snapshot" in result["explainability"]["based_on"]


def test_rules_used_contains_at_least_one_rule():
    result = generate_review(_make_version())
    assert len(result["explainability"]["rules_used"]) > 0


def test_rules_used_no_duplicates():
    """Duplicate rule entries must not appear in rules_used."""
    result = generate_review(_make_version())
    rules = result["explainability"]["rules_used"]
    assert len(rules) == len(set(rules))


def test_weakness_ids_are_unique():
    """Each weakness must carry a distinct weakness_id."""
    result = generate_review(_make_version())
    ids = [w["weakness_id"] for w in result["weaknesses"]]
    assert len(ids) == len(set(ids))
