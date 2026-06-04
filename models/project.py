import uuid
from datetime import datetime, timezone


def make_project(name: str, config: dict = None) -> dict:
    """Create a project record."""
    return {
        "project_id": str(uuid.uuid4()),
        "name": name,
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
