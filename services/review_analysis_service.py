"""
Review Analysis Service
Responsibility: generate a structured deterministic review from a version record.
Input  → version dict (contains version_summary + artifact_snapshot), optional personas list
Process → inspect summary fields and snapshot coverage; derive weaknesses, summary, explainability;
          reorder/emphasise findings based on supplied personas
Output → result dict  {summary, weaknesses, explainability}

Rules:
- No AI calls.
- No assumptions beyond available data.
- Every weakness must be traceable to a specific gap in version_summary or snapshot.
- All output keys always present.
- Persona handling is deterministic: same personas always produce same ordering.
"""

import uuid

# ---------------------------------------------------------------------------
# Summary field metadata used by weakness rules
# ---------------------------------------------------------------------------

# String fields in version_summary that are "empty" when == ""
_STRING_SUMMARY_FIELDS = (
    "client_ask",
    "solution_understanding",
    "technology_landscape",
    "delivery_model",
    "tooling_recommendations",
    "architecture_understanding",
)

# Severity mapping per missing summary field
_FIELD_SEVERITY = {
    "client_ask":              "high",
    "solution_understanding":  "high",
    "architecture_understanding": "high",
    "technology_landscape":    "medium",
    "delivery_model":          "medium",
    "tooling_recommendations": "low",
}

# Human-readable descriptions per missing field
_FIELD_DESCRIPTION = {
    "client_ask":              "No client ask artefact was found. The review cannot assess alignment to client requirements.",
    "solution_understanding":  "No solution design artefact was found. The review cannot evaluate the proposed solution.",
    "architecture_understanding": "No architecture artefact was found. The review cannot assess the technical structure.",
    "technology_landscape":    "No technology landscape artefact was found. Technology choices cannot be evaluated.",
    "delivery_model":          "No delivery model artefact was found. Timeline and delivery approach are unknown.",
    "tooling_recommendations": "No tooling artefact was found. Tool suitability cannot be assessed.",
}


# ---------------------------------------------------------------------------
# Persona → weakness category priority mapping
# ---------------------------------------------------------------------------

# Maps normalised persona key to the weakness categories that should be
# surfaced first in recommended_focus and key_findings.
_PERSONA_PRIORITY: dict = {
    "architect": ["architecture_understanding", "solution_understanding"],
    "delivery lead": ["delivery_model"],
    "security": ["constraints"],
}

# Security sentinel: if none of these summary fields contain "security",
# produce a deterministic security-context finding.
_SECURITY_SUMMARY_FIELDS = (
    "constraints",
    "tooling_recommendations",
    "technology_landscape",
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_review(version: dict, personas: list = None) -> dict:
    """
    Produce a structured deterministic review result from a version record.

    Args:
        version:  version record with version_summary and artifact_snapshot.
        personas: optional list of normalised persona keys (lowercase strings).
                  When supplied, weakness ordering and focus areas are adjusted
                  deterministically. No AI calls are made.

    Returns: {summary, weaknesses, explainability}
    """
    personas = personas or []
    version_summary = version.get("version_summary") or {}
    artifact_snapshot = version.get("artifact_snapshot") or []

    weaknesses, rules_used = _evaluate_summary_fields(version_summary)

    missing_info_weaknesses, missing_rules = _evaluate_missing_information(version_summary)
    weaknesses.extend(missing_info_weaknesses)
    rules_used.extend(missing_rules)

    coverage_weaknesses, coverage_rules = _evaluate_artifact_coverage(artifact_snapshot)
    weaknesses.extend(coverage_weaknesses)
    rules_used.extend(coverage_rules)

    if "security" in personas:
        sec_weaknesses, sec_rules = _evaluate_security_context(version_summary)
        weaknesses.extend(sec_weaknesses)
        rules_used.extend(sec_rules)

    if personas:
        weaknesses = _reorder_by_personas(weaknesses, personas)

    summary = _build_summary(weaknesses, version_summary, personas)
    explainability = _build_explainability(rules_used)

    return {
        "summary": summary,
        "weaknesses": weaknesses,
        "explainability": explainability,
    }


# ---------------------------------------------------------------------------
# Rule: empty string fields in version_summary
# ---------------------------------------------------------------------------

def _evaluate_summary_fields(version_summary: dict) -> tuple:
    """Generate one weakness per empty required string field in version_summary."""
    weaknesses = []
    rules_used = []

    for field in _STRING_SUMMARY_FIELDS:
        value = version_summary.get(field, "")
        if not value:
            weakness = _make_weakness(
                category="missing_information",
                severity=_FIELD_SEVERITY.get(field, "low"),
                description=_FIELD_DESCRIPTION.get(
                    field,
                    f"Summary field '{field}' is empty — no relevant artefact was found.",
                ),
                source_refs=[f"version_summary.{field}"],
            )
            weaknesses.append(weakness)
            rules_used.append(f"rule:empty_summary_field:{field}")

    return weaknesses, rules_used


# ---------------------------------------------------------------------------
# Rule: entries in version_summary.missing_information
# ---------------------------------------------------------------------------

def _evaluate_missing_information(version_summary: dict) -> tuple:
    """Generate one weakness per entry already flagged in missing_information."""
    weaknesses = []
    rules_used = []

    for note in version_summary.get("missing_information", []):
        # Avoid duplicating weaknesses already raised by _evaluate_summary_fields
        # (missing_information notes reference the same fields — skip if already covered)
        already_covered = any(
            field in note
            for field in _STRING_SUMMARY_FIELDS
        )
        if already_covered:
            continue

        weakness = _make_weakness(
            category="missing_information",
            severity="medium",
            description=f"Version summary flagged: {note}",
            source_refs=["version_summary.missing_information"],
        )
        weaknesses.append(weakness)
        rules_used.append("rule:missing_information_entry")

    return weaknesses, rules_used


# ---------------------------------------------------------------------------
# Rule: very limited artifact coverage (fewer than 2 artifacts)
# ---------------------------------------------------------------------------

def _evaluate_artifact_coverage(artifact_snapshot: list) -> tuple:
    """Flag a weakness when the snapshot contains fewer than 2 artifacts."""
    weaknesses = []
    rules_used = []

    if len(artifact_snapshot) < 2:
        weakness = _make_weakness(
            category="limited_coverage",
            severity="medium",
            description=(
                f"Only {len(artifact_snapshot)} artefact(s) included in this version. "
                "A richer artefact set produces a more reliable review."
            ),
            source_refs=["artifact_snapshot"],
        )
        weaknesses.append(weakness)
        rules_used.append("rule:limited_artifact_coverage")

    return weaknesses, rules_used


# ---------------------------------------------------------------------------
# Rule: security context missing (triggered only when "security" persona active)
# ---------------------------------------------------------------------------

def _evaluate_security_context(version_summary: dict) -> tuple:
    """
    Produce a deterministic weakness when no security-related content is
    detectable in any of the designated summary fields.

    Only called when the "security" persona is present.
    """
    weaknesses = []
    rules_used = []

    has_security = False
    for field in _SECURITY_SUMMARY_FIELDS:
        value = version_summary.get(field, "")
        # constraints may be a list; check each item
        if isinstance(value, list):
            if any("security" in str(item).lower() for item in value):
                has_security = True
                break
        elif isinstance(value, str) and "security" in value.lower():
            has_security = True
            break

    if not has_security:
        weakness = _make_weakness(
            category="missing_security_context",
            severity="high",
            description=(
                "Security persona active: no security-related context found in version summary. "
                "Security constraints, tooling, or controls are not documented."
            ),
            source_refs=list(_SECURITY_SUMMARY_FIELDS),
        )
        weaknesses.append(weakness)
        rules_used.append("rule:missing_security_context")

    return weaknesses, rules_used


# ---------------------------------------------------------------------------
# Persona-driven reordering
# ---------------------------------------------------------------------------

def _reorder_by_personas(weaknesses: list, personas: list) -> list:
    """
    Reorder weaknesses so that those matching persona priority categories
    appear first. Relative order within each group is preserved.
    Weaknesses not matching any persona priority are placed after.
    """
    # Build ordered list of priority category keywords from active personas
    priority_categories = []
    for persona in personas:
        for cat in _PERSONA_PRIORITY.get(persona, []):
            if cat not in priority_categories:
                priority_categories.append(cat)

    def _priority_index(weakness: dict) -> int:
        refs = " ".join(weakness.get("source_refs", []))
        desc = weakness.get("description", "").lower()
        for idx, cat in enumerate(priority_categories):
            if cat in refs or cat in desc:
                return idx
        return len(priority_categories)  # lower priority — placed after

    return sorted(weaknesses, key=_priority_index)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_summary(weaknesses: list, version_summary: dict, personas: list = None) -> dict:
    """Derive overall_assessment, key_findings, and recommended_focus.

    When personas are active the recommended_focus list is already ordered by
    _reorder_by_personas; we simply pull from the already-ordered weaknesses.
    """
    personas = personas or []
    high_count = sum(1 for w in weaknesses if w["severity"] == "high")
    medium_count = sum(1 for w in weaknesses if w["severity"] == "medium")
    total = len(weaknesses)

    if high_count > 0:
        overall = (
            f"Review identified {total} weakness(es) including {high_count} high-severity gap(s). "
            "Critical artefacts are missing. Address before proceeding."
        )
    elif medium_count > 0:
        overall = (
            f"Review identified {total} weakness(es) with {medium_count} medium-severity gap(s). "
            "Some coverage gaps exist but core artefacts are present."
        )
    elif total > 0:
        overall = (
            f"Review identified {total} low-severity weakness(es). "
            "Core artefacts are present; minor gaps noted."
        )
    else:
        overall = "All expected summary sections are covered. No weaknesses detected."

    # key_findings: high-severity items in current (potentially persona-reordered) order
    key_findings = [w["description"] for w in weaknesses if w["severity"] == "high"]

    # recommended_focus: high + medium in current order (persona reordering already applied)
    recommended_focus = [w["description"] for w in weaknesses if w["severity"] in ("high", "medium")]

    return {
        "overall_assessment": overall,
        "key_findings": key_findings,
        "recommended_focus": recommended_focus,
    }


def _build_explainability(rules_used: list) -> dict:
    """Return the explainability block listing data sources and rules applied."""
    return {
        "based_on": ["version_summary", "artifact_snapshot"],
        "rules_used": list(dict.fromkeys(rules_used)),   # preserve order, deduplicate
    }


def _make_weakness(
    category: str,
    severity: str,
    description: str,
    source_refs: list,
) -> dict:
    """Construct a single weakness record with a unique ID."""
    return {
        "weakness_id": str(uuid.uuid4()),
        "category": category,
        "severity": severity,
        "description": description,
        "source_refs": source_refs,
    }
