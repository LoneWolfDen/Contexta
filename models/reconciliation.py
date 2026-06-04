"""
Reconciliation Model
Responsibility: construct a well-shaped reconciliation record.
No business logic — pure data assembly.
"""

import uuid
from datetime import datetime, timezone


def make_reconciliation(
    source_reviews: list,
    summary: dict,
    merged_weaknesses: list,
    conflicts: list,
    explainability: dict,
) -> dict:
    """
    Build a reconciliation record.

    Args:
        source_reviews:     list of review_id strings that were merged.
        summary:            {consensus_findings, key_risks, recommended_focus}
        merged_weaknesses:  list of merged weakness dicts.
        conflicts:          list of conflict dicts (may be empty).
        explainability:     {merge_rules_used: [str, ...]}

    Returns:
        Reconciliation record dict with recon_id and created_at.
    """
    return {
        "recon_id": str(uuid.uuid4()),
        "source_reviews": source_reviews,
        "summary": summary,
        "merged_weaknesses": merged_weaknesses,
        "conflicts": conflicts,
        "explainability": explainability,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
