import uuid
from datetime import datetime, timezone


def make_review(version_id: str, project_id: str, config: dict = None) -> dict:
    """Create a review record linked to a version."""
    return {
        "review_id": str(uuid.uuid4()),
        "version_id": version_id,
        "project_id": project_id,
        "status": "mock",
        "result": {
            "weaknesses": [],
            "summary": "Mock review — AI logic not yet implemented.",
        },
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
