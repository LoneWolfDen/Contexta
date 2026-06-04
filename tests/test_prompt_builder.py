"""
Unit tests for services/prompt_builder_service.py

Tests call build_prompt_context() and resolve_personas() directly — no Flask client needed.
Covers: output shape, persona handling, security finding, architect/delivery ordering.
"""

from services.prompt_builder_service import build_prompt_context, resolve_personas
from services.review_analysis_service import generate_review

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_version(summary_overrides=None, snapshot=None, version_id="v-001"):
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
        "project_id": "p-001",
        "artifact_snapshot": snapshot or [],
        "version_summary": base_summary,
        "config": {},
    }


def _make_payload(personas=None, user_context=None):
    payload = {}
    if personas is not None:
        payload["personas"] = personas
    if user_context is not None:
        payload["user_context"] = user_context
    return payload


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_build_prompt_context_returns_dict():
    result = build_prompt_context(_make_version(), _make_payload())
    assert isinstance(result, dict)


def test_prompt_context_has_base_prompt():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "base_prompt" in result


def test_prompt_context_has_persona_prompts():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "persona_prompts" in result


def test_prompt_context_has_user_context():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "user_context" in result


def test_prompt_context_has_version_context_refs():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "version_context_refs" in result


def test_base_prompt_is_string():
    result = build_prompt_context(_make_version(), _make_payload())
    assert isinstance(result["base_prompt"], str)


def test_persona_prompts_is_list():
    result = build_prompt_context(_make_version(), _make_payload())
    assert isinstance(result["persona_prompts"], list)


def test_user_context_is_string():
    result = build_prompt_context(_make_version(), _make_payload())
    assert isinstance(result["user_context"], str)


def test_version_context_refs_is_list():
    result = build_prompt_context(_make_version(), _make_payload())
    assert isinstance(result["version_context_refs"], list)


# ---------------------------------------------------------------------------
# version_context_refs always present
# ---------------------------------------------------------------------------

def test_version_context_refs_contains_version_summary():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "version_summary" in result["version_context_refs"]


def test_version_context_refs_contains_artifact_snapshot():
    result = build_prompt_context(_make_version(), _make_payload())
    assert "artifact_snapshot" in result["version_context_refs"]


# ---------------------------------------------------------------------------
# No personas supplied
# ---------------------------------------------------------------------------

def test_no_personas_gives_empty_persona_prompts():
    result = build_prompt_context(_make_version(), _make_payload())
    assert result["persona_prompts"] == []


def test_no_user_context_gives_empty_string():
    result = build_prompt_context(_make_version(), _make_payload())
    assert result["user_context"] == ""


# ---------------------------------------------------------------------------
# base_prompt includes version_id
# ---------------------------------------------------------------------------

def test_base_prompt_references_version_id():
    version = _make_version(version_id="v-abc-123")
    result = build_prompt_context(version, _make_payload())
    assert "v-abc-123" in result["base_prompt"]


# ---------------------------------------------------------------------------
# resolve_personas — normalisation
# ---------------------------------------------------------------------------

def test_resolve_personas_returns_list():
    assert isinstance(resolve_personas([]), list)


def test_resolve_known_persona_architect():
    assert "architect" in resolve_personas(["Architect"])


def test_resolve_known_persona_delivery_lead():
    assert "delivery lead" in resolve_personas(["Delivery Lead"])


def test_resolve_known_persona_security():
    assert "security" in resolve_personas(["Security"])


def test_resolve_unknown_persona_dropped():
    assert resolve_personas(["Ghost", "Unknown"]) == []


def test_resolve_personas_deduplicates():
    result = resolve_personas(["Architect", "Architect"])
    assert result.count("architect") == 1


def test_resolve_personas_case_insensitive():
    assert "architect" in resolve_personas(["ARCHITECT"])


def test_resolve_mixed_known_unknown():
    result = resolve_personas(["Architect", "Ghost"])
    assert result == ["architect"]


# ---------------------------------------------------------------------------
# Persona prompts — structure
# ---------------------------------------------------------------------------

def test_architect_persona_prompt_has_required_keys():
    result = build_prompt_context(_make_version(), _make_payload(personas=["Architect"]))
    pp = result["persona_prompts"]
    assert len(pp) == 1
    for key in ("persona", "focus", "directive"):
        assert key in pp[0], f"Missing persona_prompt key: {key}"


def test_delivery_lead_persona_prompt_has_required_keys():
    result = build_prompt_context(_make_version(), _make_payload(personas=["Delivery Lead"]))
    pp = result["persona_prompts"]
    assert len(pp) == 1
    for key in ("persona", "focus", "directive"):
        assert key in pp[0]


def test_security_persona_prompt_has_required_keys():
    result = build_prompt_context(_make_version(), _make_payload(personas=["Security"]))
    pp = result["persona_prompts"]
    assert len(pp) == 1
    for key in ("persona", "focus", "directive"):
        assert key in pp[0]


def test_multiple_personas_produce_multiple_prompts():
    result = build_prompt_context(
        _make_version(),
        _make_payload(personas=["Architect", "Delivery Lead"]),
    )
    assert len(result["persona_prompts"]) == 2


def test_persona_prompt_persona_field_is_string():
    result = build_prompt_context(_make_version(), _make_payload(personas=["Architect"]))
    assert isinstance(result["persona_prompts"][0]["persona"], str)


# ---------------------------------------------------------------------------
# user_context passthrough
# ---------------------------------------------------------------------------

def test_user_context_is_preserved():
    payload = _make_payload(user_context="Assess cloud migration readiness.")
    result = build_prompt_context(_make_version(), payload)
    assert result["user_context"] == "Assess cloud migration readiness."


def test_none_user_context_defaults_to_empty_string():
    result = build_prompt_context(_make_version(), {"user_context": None})
    assert result["user_context"] == ""


# ---------------------------------------------------------------------------
# test_architect_persona_changes_focus
# ---------------------------------------------------------------------------

def test_architect_persona_changes_focus():
    """
    Architect persona must cause architecture-related weaknesses to appear
    first in recommended_focus.
    """
    version = _make_version()   # all summary fields empty → many weaknesses
    result = generate_review(version, personas=["architect"])
    focus = result["summary"]["recommended_focus"]
    assert len(focus) > 0
    # The first item in recommended_focus should reference architecture
    first = focus[0].lower()
    assert "architect" in first or "design" in first or "solution" in first


# ---------------------------------------------------------------------------
# test_delivery_persona_changes_focus
# ---------------------------------------------------------------------------

def test_delivery_persona_changes_focus():
    """
    Delivery Lead persona must cause delivery-related weaknesses to appear
    first in recommended_focus.
    """
    version = _make_version()
    result = generate_review(version, personas=["delivery lead"])
    focus = result["summary"]["recommended_focus"]
    assert len(focus) > 0
    first = focus[0].lower()
    assert "delivery" in first or "timeline" in first or "dependency" in first or "dependencies" in first


# ---------------------------------------------------------------------------
# test_security_persona_flags_missing_context
# ---------------------------------------------------------------------------

def test_security_persona_flags_missing_context():
    """
    Security persona on a version with no security-related content must
    produce a weakness with category 'missing_security_context'.
    """
    version = _make_version()   # no security content anywhere
    result = generate_review(version, personas=["security"])
    categories = [w["category"] for w in result["weaknesses"]]
    assert "missing_security_context" in categories


def test_security_persona_no_finding_when_security_present():
    """
    If constraints already contain a security reference, the security
    weakness must NOT be raised.
    """
    version = _make_version(summary_overrides={
        "constraints": ["security: ISO27001 compliance required"],
    })
    result = generate_review(version, personas=["security"])
    categories = [w["category"] for w in result["weaknesses"]]
    assert "missing_security_context" not in categories


def test_security_weakness_has_high_severity():
    version = _make_version()
    result = generate_review(version, personas=["security"])
    sec = [w for w in result["weaknesses"] if w["category"] == "missing_security_context"]
    assert len(sec) == 1
    assert sec[0]["severity"] == "high"


def test_security_weakness_not_raised_without_persona():
    """missing_security_context must NOT appear when security persona is absent."""
    version = _make_version()
    result = generate_review(version, personas=[])
    categories = [w["category"] for w in result["weaknesses"]]
    assert "missing_security_context" not in categories
