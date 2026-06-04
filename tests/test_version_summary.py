"""
Unit tests for services/version_summary_service.py

Tests operate directly on generate_version_summary() — no HTTP layer needed.
"""

import pytest
from services.version_summary_service import generate_version_summary, SUMMARY_FIELDS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = list(SUMMARY_FIELDS)

LIST_KEYS = {"constraints", "dependencies", "missing_information"}


def _artifact(artifact_type="document", file_path="/files/doc.pdf", project_id="p1"):
    return {
        "artifact_id": "a1",
        "project_id": project_id,
        "type": artifact_type,
        "source_type": "upload",
        "file_path": file_path,
        "included_in_review": True,
        "config": {},
    }


# ---------------------------------------------------------------------------
# test_summary_has_all_fields
# All nine keys must always be present regardless of input
# ---------------------------------------------------------------------------

def test_summary_has_all_fields_with_single_artifact():
    summary = generate_version_summary([_artifact()])
    for key in REQUIRED_KEYS:
        assert key in summary, f"Missing key: {key}"


def test_summary_has_all_fields_with_empty_snapshot():
    summary = generate_version_summary([])
    for key in REQUIRED_KEYS:
        assert key in summary, f"Missing key: {key}"


def test_summary_list_fields_are_lists():
    summary = generate_version_summary([_artifact()])
    for key in LIST_KEYS:
        assert isinstance(summary[key], list), f"Expected list for '{key}'"


def test_summary_string_fields_are_strings():
    summary = generate_version_summary([_artifact()])
    string_keys = [k for k in REQUIRED_KEYS if k not in LIST_KEYS]
    for key in string_keys:
        assert isinstance(summary[key], str), f"Expected str for '{key}'"


# ---------------------------------------------------------------------------
# test_summary_allows_empty_inputs
# Empty or minimal snapshots must not raise and must return safe empty values
# ---------------------------------------------------------------------------

def test_empty_snapshot_returns_empty_strings_and_lists():
    summary = generate_version_summary([])
    string_keys = [k for k in REQUIRED_KEYS if k not in LIST_KEYS]
    for key in string_keys:
        # architecture_understanding, client_ask, solution_understanding are required
        # so they should appear in missing_information — not in string fields
        if key != "missing_information":
            assert summary[key] == ""


def test_empty_snapshot_populates_missing_information():
    summary = generate_version_summary([])
    assert len(summary["missing_information"]) > 0


def test_empty_snapshot_flags_client_ask_missing():
    summary = generate_version_summary([])
    assert any("client_ask" in note for note in summary["missing_information"])


def test_empty_snapshot_flags_solution_understanding_missing():
    summary = generate_version_summary([])
    assert any("solution_understanding" in note for note in summary["missing_information"])


def test_empty_snapshot_flags_architecture_understanding_missing():
    summary = generate_version_summary([])
    assert any("architecture_understanding" in note for note in summary["missing_information"])


def test_artifact_with_unknown_type_does_not_raise():
    artifact = _artifact(artifact_type="unknown_type", file_path="/files/random.xyz")
    summary = generate_version_summary([artifact])
    assert isinstance(summary, dict)


# ---------------------------------------------------------------------------
# Signal matching — artifacts with recognisable types/paths fill fields
# ---------------------------------------------------------------------------

def test_brief_artifact_fills_client_ask():
    artifact = _artifact(artifact_type="brief", file_path="/files/client_brief.pdf")
    summary = generate_version_summary([artifact])
    assert summary["client_ask"] != ""


def test_architecture_artifact_fills_architecture_understanding():
    artifact = _artifact(artifact_type="architecture", file_path="/files/arch.drawio")
    summary = generate_version_summary([artifact])
    assert summary["architecture_understanding"] != ""


def test_solution_artifact_fills_solution_understanding():
    artifact = _artifact(artifact_type="solution", file_path="/files/solution_design.pdf")
    summary = generate_version_summary([artifact])
    assert summary["solution_understanding"] != ""


def test_dependency_artifact_fills_dependencies():
    artifact = _artifact(artifact_type="integration", file_path="/files/api_integration.pdf")
    summary = generate_version_summary([artifact])
    assert len(summary["dependencies"]) > 0


def test_constraint_artifact_fills_constraints():
    artifact = _artifact(artifact_type="compliance", file_path="/files/sla_requirements.pdf")
    summary = generate_version_summary([artifact])
    assert len(summary["constraints"]) > 0


def test_matching_artifact_removes_it_from_missing_information():
    """If client_ask is covered, it must NOT appear in missing_information."""
    artifact = _artifact(artifact_type="brief", file_path="/files/brief.pdf")
    summary = generate_version_summary([artifact])
    assert not any("client_ask" in note for note in summary["missing_information"])


def test_multiple_dependency_artifacts_all_recorded():
    artifacts = [
        _artifact(artifact_type="integration", file_path="/files/api_one.pdf"),
        _artifact(artifact_type="dependency", file_path="/files/dep_two.pdf"),
    ]
    summary = generate_version_summary(artifacts)
    assert len(summary["dependencies"]) == 2


def test_duplicate_label_not_added_twice():
    """Same artifact processed twice must not duplicate entries in list fields."""
    artifact = _artifact(artifact_type="integration", file_path="/files/api.pdf")
    summary = generate_version_summary([artifact, artifact])
    labels = summary["dependencies"]
    assert len(labels) == len(set(labels))
