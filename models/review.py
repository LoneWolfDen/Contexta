import uuid
from datetime import datetime, timezone


def make_review(
    version_id: str,
    project_id: str,
    result: dict = None,
    config: dict = None,
) -> dict:
    """
    Create a review record linked to a version.

    result shape (produced by review_analysis_service):
    {
        "summary":        {overall_assessment, key_findings, recommended_focus},
        "weaknesses":     [{weakness_id, category, severity, description, source_refs}],
        "explainability": {based_on, rules_used},
    }
    """
    return {
        "review_id": str(uuid.uuid4()),
        "version_id": version_id,
        "project_id": project_id,
        "status": "complete",
        "result": result or {
            "summary": {
                "overall_assessment": "",
                "key_findings": [],
                "recommended_focus": [],
            },
            "weaknesses": [],
            "explainability": {
                "based_on": [],
                "rules_used": [],
            },
        },
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
