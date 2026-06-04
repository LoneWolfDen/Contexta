"""
Reconciliation Service
Responsibility: merge multiple review results into a single deterministic reconciled output.

Input  → payload dict {review_ids: [str, ...]}
Process → fetch reviews, extract weaknesses, group by category, merge per group,
          resolve severity (max), build summary + explainability, persist record
Output → stored reconciliation dict

Rules:
- No AI calls.
- No persona logic.
- No prompt usage.
- Deterministic: same input always produces same output.
- Storage: own JSON file (recon_db.json) — store.py is not modified.
"""

import json
import os
from typing import Optional

from models.reconciliation import make_reconciliation
from storage import store

# ---------------------------------------------------------------------------
# Reconciliation-specific persistence (store.py is read-only for this sprint)
# ---------------------------------------------------------------------------

_RECON_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "recon_db.json")


def _load_recon_db() -> dict:
    path = _get_recon_db_path()
    if not os.path.exists(path):
        return {"reconciliations": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_recon_db(db: dict) -> None:
    path = _get_recon_db_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _get_recon_db_path() -> str:
    """Return the active path — can be overridden in tests via module attribute."""
    return _RECON_DB_PATH


def _insert_reconciliation(record: dict) -> dict:
    db = _load_recon_db()
    db["reconciliations"][record["recon_id"]] = record
    _save_recon_db(db)
    return record


def get_reconciliation(recon_id: str) -> Optional[dict]:
    db = _load_recon_db()
    return db["reconciliations"].get(recon_id)


def get_all_reconciliations() -> list:
    db = _load_recon_db()
    return list(db["reconciliations"].values())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_reconciliation(payload: dict) -> dict:
    """
    Merge the reviews identified by payload["review_ids"] into one record.

    Raises ValueError for invalid or missing review_ids.
    """
    _validate(payload)

    review_ids = payload["review_ids"]
    reviews = _fetch_reviews(review_ids)

    all_weaknesses = _extract_weaknesses(reviews)
    grouped = _group_by_category(all_weaknesses)
    merged_weaknesses = [_merge_group(category, items) for category, items in grouped.items()]

    summary = _build_summary(merged_weaknesses)
    conflicts = _detect_conflicts(grouped)
    explainability = _build_explainability()

    record = make_reconciliation(
        source_reviews=review_ids,
        summary=summary,
        merged_weaknesses=merged_weaknesses,
        conflicts=conflicts,
        explainability=explainability,
    )
    return _insert_reconciliation(record)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(payload: dict) -> None:
    review_ids = payload.get("review_ids")
    if not review_ids:
        raise ValueError("Missing required field: review_ids must be a non-empty list.")
    if not isinstance(review_ids, list):
        raise ValueError("review_ids must be a list.")
    if len(review_ids) == 0:
        raise ValueError("review_ids must contain at least one review_id.")


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _fetch_reviews(review_ids: list) -> list:
    """Fetch each review from store; raise ValueError for any missing id."""
    reviews = []
    missing = []
    for rid in review_ids:
        review = store.get_review(rid)
        if review is None:
            missing.append(rid)
        else:
            reviews.append(review)
    if missing:
        raise ValueError(f"review_id(s) not found: {', '.join(missing)}")
    return reviews


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_weaknesses(reviews: list) -> list:
    """
    Pull all weakness dicts out of every review result.
    Attach source_review_id to each weakness for traceability.
    """
    collected = []
    for review in reviews:
        result = review.get("result") or {}
        for weakness in result.get("weaknesses") or []:
            enriched = dict(weakness)
            enriched["source_review_id"] = review["review_id"]
            collected.append(enriched)
    return collected


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_by_category(weaknesses: list) -> dict:
    """
    Group weakness dicts by their 'category' field.
    Returns {category: [weakness, ...]} ordered by first-seen category.
    """
    groups: dict = {}
    for w in weaknesses:
        cat = w.get("category", "unknown")
        groups.setdefault(cat, []).append(w)
    return groups


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _resolve_severity(weaknesses: list) -> str:
    """Return the highest severity found across the group."""
    best = "low"
    for w in weaknesses:
        sev = w.get("severity", "low")
        if _SEVERITY_RANK.get(sev, 0) > _SEVERITY_RANK[best]:
            best = sev
    return best


def _deduplicate_descriptions(weaknesses: list) -> list:
    """Return unique description strings, preserving order."""
    seen = []
    for w in weaknesses:
        desc = w.get("description", "").strip()
        if desc and desc not in seen:
            seen.append(desc)
    return seen


def _collect_source_reviews(weaknesses: list) -> list:
    """Return unique source_review_id values, preserving order."""
    seen = []
    for w in weaknesses:
        rid = w.get("source_review_id")
        if rid and rid not in seen:
            seen.append(rid)
    return seen


def _merge_group(category: str, weaknesses: list) -> dict:
    """
    Produce one merged weakness from a group sharing the same category.

    Merge rules:
    - severity  → max across group
    - descriptions → deduplicated list
    - source_reviews → all contributing review ids
    """
    severity = _resolve_severity(weaknesses)
    descriptions = _deduplicate_descriptions(weaknesses)
    source_reviews = _collect_source_reviews(weaknesses)

    return {
        "category": category,
        "severity": severity,
        "descriptions": descriptions,
        "source_reviews": source_reviews,
        "count": len(weaknesses),
    }


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def _detect_conflicts(grouped: dict) -> list:
    """
    A conflict exists when weaknesses in the same category carry different
    severities across source reviews (e.g., one says 'low', another 'high').
    Returns one conflict record per such category.
    """
    conflicts = []
    for category, weaknesses in grouped.items():
        severities = {w.get("severity", "low") for w in weaknesses}
        if len(severities) > 1:
            conflicts.append({
                "category": category,
                "conflicting_severities": sorted(severities),
                "resolution": "severity_max",
            })
    return conflicts


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(merged_weaknesses: list) -> dict:
    """
    Derive consensus_findings, key_risks, and recommended_focus
    from the merged weakness list.
    """
    high_items = [w for w in merged_weaknesses if w["severity"] == "high"]
    medium_items = [w for w in merged_weaknesses if w["severity"] == "medium"]

    consensus_findings = [w["category"] for w in merged_weaknesses]

    key_risks = [
        desc
        for w in high_items
        for desc in w["descriptions"]
    ]

    recommended_focus = [
        desc
        for w in (high_items + medium_items)
        for desc in w["descriptions"]
    ]

    return {
        "consensus_findings": consensus_findings,
        "key_risks": key_risks,
        "recommended_focus": recommended_focus,
    }


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------

def _build_explainability() -> dict:
    return {
        "merge_rules_used": [
            "group_by_category",
            "severity_max",
            "deduplicate_similar_descriptions",
        ]
    }
