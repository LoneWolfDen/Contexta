"""
Proposal Service
Responsibility: generate a structured proposal from a review or reconciliation.

Input  → payload dict {review_id: str} OR {recon_id: str}
Process → fetch source, extract weaknesses, transform to recommendations,
          build structured proposal output, persist record
Output → stored proposal dict

Rules:
- No AI calls.
- Deterministic: same input always produces the same output.
- Storage: own JSON file (proposal_db.json) — store.py is not modified.
- Traceability: Project → Version → Review → Reconciliation → Proposal
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from storage import store
from services import reconciliation_service


# ---------------------------------------------------------------------------
# Proposal-specific persistence
# ---------------------------------------------------------------------------

_PROPOSAL_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "storage", "proposal_db.json"
)


def _get_proposal_db_path() -> str:
    """Return active path — can be overridden in tests via module attribute."""
    return _PROPOSAL_DB_PATH


def _load_proposal_db() -> dict:
    path = _get_proposal_db_path()
    if not os.path.exists(path):
        return {"proposals": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_proposal_db(db: dict) -> None:
    path = _get_proposal_db_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _insert_proposal(record: dict) -> dict:
    db = _load_proposal_db()
    db["proposals"][record["proposal_id"]] = record
    _save_proposal_db(db)
    return record


def get_proposal(proposal_id: str) -> Optional[dict]:
    db = _load_proposal_db()
    return db["proposals"].get(proposal_id)


def get_all_proposals() -> list:
    db = _load_proposal_db()
    return list(db["proposals"].values())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_proposal(payload: dict) -> dict:
    """
    Generate a structured proposal from a review or reconciliation.

    Raises ValueError for missing/invalid input or unknown IDs.
    """
    _validate(payload)

    review_id = payload.get("review_id")
    recon_id = payload.get("recon_id")

    if review_id:
        source_type = "review"
        source_id = review_id
        weaknesses = _weaknesses_from_review(review_id)
        source_refs = [review_id]
    else:
        source_type = "reconciliation"
        source_id = recon_id
        weaknesses = _weaknesses_from_reconciliation(recon_id)
        recon = reconciliation_service.get_reconciliation(recon_id)
        source_refs = recon.get("source_reviews", [])

    recommendations = _build_recommendations(weaknesses)
    summary = _build_summary(weaknesses, recommendations)
    delivery_considerations = _build_delivery_considerations(weaknesses)
    kpis = _build_kpis(weaknesses)
    references = _build_references(source_refs, source_type, source_id)

    record = {
        "proposal_id": str(uuid.uuid4()),
        "source_type": source_type,
        "source_id": source_id,
        "source_refs": source_refs,
        "summary": summary,
        "recommendations": recommendations,
        "delivery_considerations": delivery_considerations,
        "kpis": kpis,
        "references": references,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return _insert_proposal(record)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(payload: dict) -> None:
    if not payload:
        raise ValueError("Request body is required.")

    review_id = payload.get("review_id")
    recon_id = payload.get("recon_id")

    if not review_id and not recon_id:
        raise ValueError("Either 'review_id' or 'recon_id' is required.")

    if review_id and recon_id:
        raise ValueError("Provide either 'review_id' or 'recon_id', not both.")


# ---------------------------------------------------------------------------
# Weakness extraction
# ---------------------------------------------------------------------------

def _weaknesses_from_review(review_id: str) -> list:
    """Fetch a review and return its weakness list."""
    review = store.get_review(review_id)
    if review is None:
        raise ValueError(f"review_id '{review_id}' does not exist.")
    result = review.get("result") or {}
    return result.get("weaknesses") or []


def _weaknesses_from_reconciliation(recon_id: str) -> list:
    """
    Fetch a reconciliation and normalise its merged_weaknesses into the
    same shape as review weaknesses so downstream logic is uniform.

    Merged weakness shape: {category, severity, descriptions, source_reviews, count}
    Normalised output:     {category, severity, description}
    """
    recon = reconciliation_service.get_reconciliation(recon_id)
    if recon is None:
        raise ValueError(f"recon_id '{recon_id}' does not exist.")

    normalised = []
    for mw in recon.get("merged_weaknesses") or []:
        descriptions = mw.get("descriptions") or []
        # Combine multiple descriptions into one representative string
        combined = "; ".join(descriptions) if descriptions else mw.get("category", "")
        normalised.append({
            "category": mw.get("category", "unknown"),
            "severity": mw.get("severity", "low"),
            "description": combined,
        })
    return normalised


# ---------------------------------------------------------------------------
# Recommendation builder
# ---------------------------------------------------------------------------

_PRIORITY_MAP = {"high": "high", "medium": "medium", "low": "low"}

# Category → actionable recommendation template
_RECOMMENDATION_TEMPLATES = {
    "requirements": "Document and formalise all requirements with explicit acceptance criteria.",
    "architecture": "Review and validate the proposed architecture against non-functional requirements.",
    "security": "Conduct a security assessment and apply relevant controls before delivery.",
    "performance": "Define performance benchmarks and validate the solution against them.",
    "scalability": "Design the solution with horizontal scalability in mind and document scaling limits.",
    "delivery": "Establish a clear delivery plan with milestones, owners, and risk mitigations.",
    "testing": "Define a test strategy covering unit, integration, and acceptance testing.",
    "documentation": "Produce or update documentation to reflect the current state of the solution.",
    "governance": "Establish governance processes for change control and decision traceability.",
    "integration": "Define and validate all integration points with clear contracts and error handling.",
    "data": "Review data models, flows, and retention policies to ensure correctness and compliance.",
    "operations": "Define operational runbooks, monitoring thresholds, and incident response procedures.",
    "cost": "Perform a cost analysis and document assumptions and constraints.",
    "risk": "Identify, classify, and mitigate risks using a formal risk register.",
    "compliance": "Assess compliance requirements and map controls to obligations.",
    "unknown": "Investigate the identified weakness and produce a targeted remediation plan.",
}


def _recommendation_for_category(category: str) -> str:
    key = category.lower().strip()
    for template_key, text in _RECOMMENDATION_TEMPLATES.items():
        if template_key in key or key in template_key:
            return text
    return _RECOMMENDATION_TEMPLATES["unknown"]


def _build_recommendations(weaknesses: list) -> list:
    """
    Convert each weakness into one recommendation.

    Rules:
    - missing_information type → actionable recommendation
    - severity → priority (high / medium / low)
    - category → recommendation text from template
    """
    seen_categories = set()
    recommendations = []

    for weakness in weaknesses:
        category = weakness.get("category", "unknown")
        severity = weakness.get("severity", "low")
        description = weakness.get("description", "")

        # Deduplicate: one recommendation per category
        cat_key = category.lower().strip()
        if cat_key in seen_categories:
            continue
        seen_categories.add(cat_key)

        recommendation_text = _recommendation_for_category(category)

        # If description mentions missing information, prepend a specific note
        if description and "missing" in description.lower():
            recommendation_text = (
                f"Address missing information: {description}. "
                + recommendation_text
            )

        recommendations.append({
            "category": category,
            "recommendation": recommendation_text,
            "priority": _PRIORITY_MAP.get(severity, "low"),
        })

    # Sort: high → medium → low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 2))

    return recommendations


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(weaknesses: list, recommendations: list) -> dict:
    total = len(weaknesses)
    high_count = sum(1 for w in weaknesses if w.get("severity") == "high")
    medium_count = sum(1 for w in weaknesses if w.get("severity") == "medium")
    low_count = sum(1 for w in weaknesses if w.get("severity") == "low")

    categories = list({w.get("category", "unknown") for w in weaknesses})

    if high_count > 0:
        risk_level = "high"
    elif medium_count > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    executive_summary = (
        f"Analysis identified {total} weakness(es) across {len(categories)} area(s). "
        f"Risk level: {risk_level}. "
        f"Breakdown — High: {high_count}, Medium: {medium_count}, Low: {low_count}."
    )

    problem_statement = (
        f"The following areas require attention: {', '.join(sorted(categories))}."
        if categories
        else "No specific areas of concern were identified."
    )

    top_recommendations = [r["recommendation"] for r in recommendations[:3]]
    if top_recommendations:
        recommended_solution = (
            "Priority actions: " + " | ".join(top_recommendations)
        )
    else:
        recommended_solution = "No specific recommendations at this time."

    return {
        "executive_summary": executive_summary,
        "problem_statement": problem_statement,
        "recommended_solution": recommended_solution,
    }


# ---------------------------------------------------------------------------
# Delivery considerations builder
# ---------------------------------------------------------------------------

_HIGH_SEVERITY_DELIVERY_NOTE = (
    "High severity issues must be resolved before delivery. "
    "Conduct a focused review session with all stakeholders."
)
_MEDIUM_SEVERITY_DELIVERY_NOTE = (
    "Medium severity issues should be tracked and addressed within the delivery timeline."
)
_DEFAULT_DELIVERY_NOTE = (
    "No critical blockers identified. Proceed with standard delivery governance."
)


def _build_delivery_considerations(weaknesses: list) -> list:
    considerations = []
    severities = {w.get("severity", "low") for w in weaknesses}

    if "high" in severities:
        considerations.append(_HIGH_SEVERITY_DELIVERY_NOTE)

    if "medium" in severities:
        considerations.append(_MEDIUM_SEVERITY_DELIVERY_NOTE)

    if not considerations:
        considerations.append(_DEFAULT_DELIVERY_NOTE)

    considerations.append(
        "Ensure traceability from requirements through to delivery artefacts."
    )
    considerations.append(
        "Schedule a post-delivery review to validate that all weaknesses have been addressed."
    )

    return considerations


# ---------------------------------------------------------------------------
# KPI builder
# ---------------------------------------------------------------------------

_CATEGORY_KPIS = {
    "security": [
        "Zero critical vulnerabilities at time of go-live.",
        "100% of security controls verified before deployment.",
    ],
    "performance": [
        "Response time within agreed SLA thresholds.",
        "Zero performance regressions in production.",
    ],
    "testing": [
        "Test coverage >= 80% across all critical paths.",
        "Zero unresolved P1/P2 defects at release.",
    ],
    "delivery": [
        "On-time delivery against agreed milestone plan.",
        "Stakeholder sign-off obtained before each phase gate.",
    ],
    "documentation": [
        "All documentation reviewed and approved before go-live.",
        "Documentation kept current throughout delivery.",
    ],
    "architecture": [
        "Architecture sign-off obtained from lead architect.",
        "No critical architecture deviations without approval.",
    ],
    "requirements": [
        "All requirements baselined and accepted by stakeholders.",
        "Requirement traceability matrix maintained throughout delivery.",
    ],
    "risk": [
        "Risk register reviewed at each sprint/milestone.",
        "All high risks have a documented mitigation plan.",
    ],
}

_DEFAULT_KPIS = [
    "All identified weaknesses resolved prior to delivery.",
    "Stakeholder acceptance criteria met and signed off.",
    "Delivery completed within agreed timeline and budget.",
]


def _build_kpis(weaknesses: list) -> list:
    kpis = []
    seen = set()
    categories = {w.get("category", "unknown").lower().strip() for w in weaknesses}

    for category in categories:
        for template_key, items in _CATEGORY_KPIS.items():
            if template_key in category or category in template_key:
                for item in items:
                    if item not in seen:
                        seen.add(item)
                        kpis.append(item)

    for item in _DEFAULT_KPIS:
        if item not in seen:
            seen.add(item)
            kpis.append(item)

    return kpis


# ---------------------------------------------------------------------------
# References builder
# ---------------------------------------------------------------------------

def _build_references(source_refs: list, source_type: str, source_id: str) -> list:
    references = [
        {
            "type": source_type,
            "id": source_id,
            "note": f"Primary source for this proposal ({source_type}).",
        }
    ]

    for ref_id in source_refs:
        if ref_id != source_id:
            references.append({
                "type": "review",
                "id": ref_id,
                "note": "Contributing review included in source reconciliation.",
            })

    return references
