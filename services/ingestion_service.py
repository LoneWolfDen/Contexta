"""
Ingestion Service
Responsibility: validate and persist artifact records.
Input  → raw artifact payload
Process → validate required fields, build record
Output → stored artifact dict
"""

from models.artifact import make_artifact
from storage import store


REQUIRED_FIELDS = ("project_id", "type", "source_type", "file_path")


def ingest_artifact(payload: dict) -> dict:
    """Validate payload, create artifact record, persist and return it."""
    _validate(payload)

    project = store.get_project(payload["project_id"])
    if project is None:
        raise ValueError(f"project_id '{payload['project_id']}' does not exist.")

    record = make_artifact(
        project_id=payload["project_id"],
        artifact_type=payload["type"],
        source_type=payload["source_type"],
        file_path=payload["file_path"],
        included_in_review=payload.get("included_in_review", True),
        config=payload.get("config", {}),
    )
    return store.insert_artifact(record)


def list_artifacts() -> list:
    """Return all stored artifacts."""
    return store.get_all_artifacts()


def _validate(payload: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
