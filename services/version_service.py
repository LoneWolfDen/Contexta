"""
Version Service
Responsibility: validate artifact selection, snapshot artifacts, persist version.
Input  → project_id + artifact_ids[]
Process → verify project and artifacts exist, build snapshot, generate summary, store version
Output → stored version dict
"""

from models.version import make_version
from services.version_summary_service import generate_version_summary
from storage import store


def create_version(payload: dict) -> dict:
    """Build a version from a list of artifact IDs and persist it."""
    _validate(payload)

    project_id = payload["project_id"]
    artifact_ids = payload["artifact_ids"]

    project = store.get_project(project_id)
    if project is None:
        raise ValueError(f"project_id '{project_id}' does not exist.")

    snapshot = _build_snapshot(artifact_ids, project_id)
    summary = generate_version_summary(snapshot)

    record = make_version(
        project_id=project_id,
        artifact_snapshot=snapshot,
        version_summary=summary,
        config=payload.get("config", {}),
    )
    return store.insert_version(record)


def list_versions() -> list:
    """Return all stored versions."""
    return store.get_all_versions()


def _validate(payload: dict) -> None:
    if not payload.get("project_id"):
        raise ValueError("Missing required field: project_id")
    if not payload.get("artifact_ids") or not isinstance(payload["artifact_ids"], list):
        raise ValueError("artifact_ids must be a non-empty list.")


def _build_snapshot(artifact_ids: list, project_id: str) -> list:
    """Fetch artifact records, verify ownership, return snapshot.

    Raises if any ID is missing or belongs to a different project.
    """
    found = store.get_artifacts_by_ids(artifact_ids)
    found_ids = {a["artifact_id"] for a in found}
    missing = [aid for aid in artifact_ids if aid not in found_ids]
    if missing:
        raise ValueError(f"artifact_ids not found: {missing}")

    cross_project = [
        a["artifact_id"] for a in found if a["project_id"] != project_id
    ]
    if cross_project:
        raise ValueError(
            f"artifact_ids do not belong to project '{project_id}': {cross_project}"
        )

    return found
