import uuid
from datetime import datetime, timezone


def make_artifact(
    project_id: str,
    artifact_type: str,
    source_type: str,
    file_path: str,
    included_in_review: bool = True,
    config: dict = None,
) -> dict:
    """Create an artifact record."""
    return {
        "artifact_id": str(uuid.uuid4()),
        "project_id": project_id,
        "type": artifact_type,
        "source_type": source_type,
        "file_path": file_path,
        "included_in_review": included_in_review,
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
