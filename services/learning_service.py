"""
Learning Service
Responsibility: extract reusable intelligence from prior outputs and generate
                controlled, non-automated improvement suggestions.

Input  → payload dict {source_type: "proposal|reconciliation|review", source_id: str}
Process → fetch source, extract weaknesses + recommendations, apply deterministic
          pattern rules, generate insights, prompt suggestions, reusable patterns
Output → stored learning record (approved = false, never auto-applied)

Rules:
- No AI calls.
- No auto-application of suggestions.
- Deterministic: same input always produces same output structure.
- Storage: own JSON file (learning_db.json) — store.py is not modified.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from storage import store
from services import reconciliation_service, proposal_service


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SOURCE_TYPES = ("proposal", "reconciliation", "review")

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}

# Minimum occurrences of the same category across weaknesses to raise an insight
_REPEAT_THRESHOLD = 2

# Category → prompt suggestion template
_PROMPT_SUGGESTIONS = {
    "security": (
        "Add a dedicated security validation step to the review prompt. "
        "Ensure security controls, threat model, and compliance requirements are explicitly checked."
    ),
    "missing_security_context": (
        "Add a dedicated security validation step to the review prompt. "
        "Ensure security controls, threat model, and compliance requirements are explicitly checked."
    ),
    "architecture": (
        "Extend the architecture review step to validate non-functional requirements, "
        "scalability limits, and component boundaries."
    ),
    "requirements": (
        "Add a requirements traceability check to the review prompt. "
        "Confirm all acceptance criteria are documented and testable."
    ),
    "delivery": (
        "Include a delivery risk assessment step in the review prompt covering milestones, "
        "dependencies, and resource availability."
    ),
    "testing": (
        "Add a test strategy validation step to the review prompt covering unit, "
        "integration, and acceptance testing coverage."
    ),
    "documentation": (
        "Include a documentation completeness check in the review prompt. "
        "Ensure all artefacts are reviewed and up to date."
    ),
    "missing_information": (
        "Add an artefact completeness gate to the review prompt. "
        "Require mandatory artefacts before proceeding to detailed review."
    ),
    "limited_coverage": (
        "Prompt should require a minimum artefact coverage check before running a review. "
        "Flag versions with fewer than two artefacts."
    ),
    "governance": (
        "Include a governance and change-control validation step in the review prompt."
    ),
    "risk": (
        "Add a risk register validation step to the review prompt. "
        "Verify that all high risks have documented mitigation plans."
    ),
    "compliance": (
        "Add a compliance mapping step to the review prompt. "
        "Ensure regulatory and contractual obligations are traced to controls."
    ),
    "performance": (
        "Include a performance and SLA validation step in the review prompt."
    ),
    "data": (
        "Add a data model and retention policy review step to the prompt."
    ),
    "integration": (
        "Include an integration contract validation step in the review prompt. "
        "Confirm all interfaces have error handling and clear ownership."
    ),
}

_DEFAULT_PROMPT_SUGGESTION = (
    "Review the prompt for the '{category}' area and add explicit validation steps "
    "to catch recurring issues in this category."
)

# Category → reusable pattern template
_PATTERN_TEMPLATES = {
    "missing_information": {
        "pattern": "missing_artefacts → high_delivery_risk",
        "description": (
            "When required artefacts are missing, delivery risk is elevated. "
            "Apply artefact completeness gate before review."
        ),
    },
    "missing_security_context": {
        "pattern": "missing_security → high_risk",
        "description": (
            "Absence of security context correlates with high risk. "
            "Security persona and dedicated security prompt step are recommended."
        ),
    },
    "limited_coverage": {
        "pattern": "sparse_version → unreliable_review",
        "description": (
            "Versions with fewer than two artefacts produce lower-confidence reviews. "
            "Enforce minimum artefact threshold."
        ),
    },
    "architecture": {
        "pattern": "architecture_gap → delivery_risk",
        "description": (
            "Unresolved architecture weaknesses increase delivery risk. "
            "Architect persona review is recommended."
        ),
    },
    "security": {
        "pattern": "missing_security → high_risk",
        "description": (
            "Security gaps consistently correlate with high-severity findings. "
            "Mandatory security review step is recommended."
        ),
    },
    "requirements": {
        "pattern": "untraced_requirements → acceptance_risk",
        "description": (
            "Missing or untraceable requirements increase the risk of acceptance failure. "
            "Requirements traceability matrix should be mandatory."
        ),
    },
    "testing": {
        "pattern": "insufficient_testing → quality_risk",
        "description": (
            "Weak test coverage correlates with quality incidents in delivery. "
            "Test strategy sign-off should be a delivery gate."
        ),
    },
    "delivery": {
        "pattern": "unclear_delivery_model → schedule_risk",
        "description": (
            "Absence of a defined delivery model raises schedule and resource risk. "
            "Delivery plan should be mandatory before review."
        ),
    },
}

_DEFAULT_PATTERN = {
    "pattern": "{category} → delivery_risk",
    "description": (
        "Recurring issues in the '{category}' category are associated with elevated delivery risk."
    ),
}


# ---------------------------------------------------------------------------
# Learning-specific persistence
# ---------------------------------------------------------------------------

_LEARNING_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "storage", "learning_db.json"
)


def _get_learning_db_path() -> str:
    """Return active path — can be overridden in tests via module attribute."""
    return _LEARNING_DB_PATH


def _load_learning_db() -> dict:
    path = _get_learning_db_path()
    if not os.path.exists(path):
        return {"learnings": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_learning_db(db: dict) -> None:
    path = _get_learning_db_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _insert_learning(record: dict) -> dict:
    db = _load_learning_db()
    db["learnings"][record["learning_id"]] = record
    _save_learning_db(db)
    return record


def get_learning(learning_id: str) -> Optional[dict]:
    db = _load_learning_db()
    return db["learnings"].get(learning_id)


def get_all_learnings() -> list:
    db = _load_learning_db()
    return list(db["learnings"].values())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_learning(payload: dict) -> dict:
    """
    Extract learning intelligence from a prior output and persist a learning record.

    Raises ValueError for invalid input or unknown source IDs.
    """
    _validate(payload)

    source_type = payload["source_type"]
    source_id = payload["source_id"]

    weaknesses, recommendations = _fetch_source(source_type, source_id)

    insights = _generate_insights(weaknesses)
    suggested_prompt_updates = _generate_prompt_suggestions(weaknesses)
    reusable_patterns = _generate_reusable_patterns(weaknesses)

    record = {
        "learning_id": str(uuid.uuid4()),
        "source_type": source_type,
        "source_id": source_id,
        "insights": insights,
        "suggested_prompt_updates": suggested_prompt_updates,
        "reusable_patterns": reusable_patterns,
        "approved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return _insert_learning(record)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(payload: dict) -> None:
    if not payload:
        raise ValueError("Request body is required.")

    source_type = payload.get("source_type")
    source_id = payload.get("source_id")

    if not source_type:
        raise ValueError("Missing required field: source_type.")
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            f"Invalid source_type '{source_type}'. "
            f"Must be one of: {', '.join(VALID_SOURCE_TYPES)}."
        )
    if not source_id:
        raise ValueError("Missing required field: source_id.")


# ---------------------------------------------------------------------------
# Source fetch
# ---------------------------------------------------------------------------

def _fetch_source(source_type: str, source_id: str) -> tuple:
    """
    Fetch the source record and return (weaknesses, recommendations).

    Normalises each source type into a uniform list of weakness dicts:
        {category, severity, description}
    """
    if source_type == "review":
        return _from_review(source_id)
    if source_type == "reconciliation":
        return _from_reconciliation(source_id)
    if source_type == "proposal":
        return _from_proposal(source_id)
    # Guard — already caught by _validate
    raise ValueError(f"Unsupported source_type: {source_type}")


def _from_review(review_id: str) -> tuple:
    review = store.get_review(review_id)
    if review is None:
        raise ValueError(f"review_id '{review_id}' does not exist.")
    result = review.get("result") or {}
    weaknesses = result.get("weaknesses") or []
    # Reviews do not carry a top-level recommendations list; use empty list
    return _normalise_weaknesses(weaknesses), []


def _from_reconciliation(recon_id: str) -> tuple:
    recon = reconciliation_service.get_reconciliation(recon_id)
    if recon is None:
        raise ValueError(f"recon_id '{recon_id}' does not exist.")

    # Merged weaknesses have shape: {category, severity, descriptions, ...}
    raw = recon.get("merged_weaknesses") or []
    weaknesses = []
    for mw in raw:
        descriptions = mw.get("descriptions") or []
        combined = "; ".join(descriptions) if descriptions else mw.get("category", "")
        weaknesses.append({
            "category": mw.get("category", "unknown"),
            "severity": mw.get("severity", "low"),
            "description": combined,
        })

    # Extract recommended_focus from summary as proxy for recommendations
    summary = recon.get("summary") or {}
    recommendations = summary.get("recommended_focus") or []
    return weaknesses, recommendations


def _from_proposal(proposal_id: str) -> tuple:
    proposal = proposal_service.get_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"proposal_id '{proposal_id}' does not exist.")

    # Proposals carry structured recommendations; derive synthetic weaknesses from them
    raw_recs = proposal.get("recommendations") or []
    weaknesses = []
    for rec in raw_recs:
        weaknesses.append({
            "category": rec.get("category", "unknown"),
            "severity": rec.get("priority", "low"),    # priority maps to severity scale
            "description": rec.get("recommendation", ""),
        })

    recommendations = [r.get("recommendation", "") for r in raw_recs]
    return weaknesses, recommendations


def _normalise_weaknesses(weaknesses: list) -> list:
    """Ensure each weakness carries at minimum {category, severity, description}."""
    normalised = []
    for w in weaknesses:
        normalised.append({
            "category": w.get("category", "unknown"),
            "severity": w.get("severity", "low"),
            "description": w.get("description", ""),
        })
    return normalised


# ---------------------------------------------------------------------------
# Insight generation
# ---------------------------------------------------------------------------

def _generate_insights(weaknesses: list) -> list:
    """
    Rules:
    1. Repeated category (>= _REPEAT_THRESHOLD occurrences) → pattern insight.
    2. Any high-severity weakness → severity insight.

    Returns a deduplicated list of insight strings.
    """
    insights = []
    seen = set()

    # Rule 1 — repeated category
    category_counts: dict = {}
    for w in weaknesses:
        cat = w.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat, count in sorted(category_counts.items()):
        if count >= _REPEAT_THRESHOLD:
            text = (
                f"Repeated weakness in category '{cat}' detected across {count} occurrence(s). "
                "This pattern suggests a systemic gap that should be addressed proactively."
            )
            if text not in seen:
                seen.add(text)
                insights.append({"type": "repeated_pattern", "category": cat, "detail": text})

    # Rule 2 — high severity
    for w in weaknesses:
        if w.get("severity") == "high":
            cat = w.get("category", "unknown")
            text = (
                f"High-severity finding in category '{cat}': {w.get('description', '')}. "
                "Prioritise remediation before next delivery stage."
            )
            if text not in seen:
                seen.add(text)
                insights.append({"type": "high_severity_pattern", "category": cat, "detail": text})

    return insights


# ---------------------------------------------------------------------------
# Prompt suggestion generation
# ---------------------------------------------------------------------------

def _generate_prompt_suggestions(weaknesses: list) -> list:
    """
    Generate one suggested prompt update per unique category present in weaknesses.
    Returns a deduplicated list of suggestion dicts.
    """
    seen_categories: set = set()
    suggestions = []

    for w in weaknesses:
        cat = w.get("category", "unknown").lower().strip()
        if cat in seen_categories:
            continue
        seen_categories.add(cat)

        suggestion_text = _prompt_suggestion_for_category(cat)
        suggestions.append({
            "category": cat,
            "suggestion": suggestion_text,
            "approved": False,
        })

    return suggestions


def _prompt_suggestion_for_category(category: str) -> str:
    """Return the matching prompt suggestion text or a formatted default."""
    # Exact match first
    if category in _PROMPT_SUGGESTIONS:
        return _PROMPT_SUGGESTIONS[category]
    # Partial match
    for key, text in _PROMPT_SUGGESTIONS.items():
        if key in category or category in key:
            return text
    return _DEFAULT_PROMPT_SUGGESTION.format(category=category)


# ---------------------------------------------------------------------------
# Reusable pattern generation
# ---------------------------------------------------------------------------

def _generate_reusable_patterns(weaknesses: list) -> list:
    """
    Generate one reusable pattern per unique category present in weaknesses.
    Returns a deduplicated list of pattern dicts.
    """
    seen_categories: set = set()
    patterns = []

    # Sort by severity descending so highest-risk patterns appear first
    sorted_weaknesses = sorted(
        weaknesses,
        key=lambda w: _SEVERITY_RANK.get(w.get("severity", "low"), 0),
        reverse=True,
    )

    for w in sorted_weaknesses:
        cat = w.get("category", "unknown").lower().strip()
        if cat in seen_categories:
            continue
        seen_categories.add(cat)

        template = _pattern_for_category(cat)
        patterns.append({
            "category": cat,
            "pattern": template["pattern"].format(category=cat),
            "description": template["description"].format(category=cat),
            "severity": w.get("severity", "low"),
        })

    return patterns


def _pattern_for_category(category: str) -> dict:
    """Return the matching pattern template or a formatted default."""
    if category in _PATTERN_TEMPLATES:
        return _PATTERN_TEMPLATES[category]
    for key, template in _PATTERN_TEMPLATES.items():
        if key in category or category in key:
            return template
    return _DEFAULT_PATTERN
