import uuid
from datetime import datetime, timezone


def make_version(project_id: str, artifact_snapshot: list, config: dict = None) -> dict:
    """Create a version record with a snapshot of selected artifacts."""
    return {
        "version_id": str(uuid.uuid4()),
        "project_id": project_id,
        "artifact_snapshot": artifact_snapshot,
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
