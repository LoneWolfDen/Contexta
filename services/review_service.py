"""
Review Service
Responsibility: validate version exists, create mock review, persist it.
Input  → version_id
Process → verify version + project exist, build mock review record
Output → stored review dict

AI logic is NOT implemented in Sprint 0.
The review result is a deterministic mock.
"""

from models.review import make_review
from storage import store


def create_review(payload: dict) -> dict:
    """Create a mock review linked to a version and persist it."""
    _validate(payload)

    version_id = payload["version_id"]
    version = store.get_version(version_id)
    if version is None:
        raise ValueError(f"version_id '{version_id}' does not exist.")

    record = make_review(
        version_id=version_id,
        project_id=version["project_id"],
        config=payload.get("config", {}),
    )
    return store.insert_review(record)


def list_reviews() -> list:
    """Return all stored reviews."""
    return store.get_all_reviews()


def _validate(payload: dict) -> None:
    if not payload.get("version_id"):
        raise ValueError("Missing required field: version_id")
