import json
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")

EMPTY_DB = {
    "projects": {},
    "artifacts": {},
    "versions": {},
    "reviews": {},
}


def _load() -> dict:
    """Load the full database from disk."""
    if not os.path.exists(DB_PATH):
        return {k: dict(v) for k, v in EMPTY_DB.items()}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(db: dict) -> None:
    """Persist the full database to disk."""
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


# --- projects ---

def insert_project(record: dict) -> dict:
    db = _load()
    db["projects"][record["project_id"]] = record
    _save(db)
    return record


def get_all_projects() -> list:
    db = _load()
    return list(db["projects"].values())


def get_project(project_id: str) -> Optional[dict]:
    db = _load()
    return db["projects"].get(project_id)


# --- artifacts ---

def insert_artifact(record: dict) -> dict:
    db = _load()
    db["artifacts"][record["artifact_id"]] = record
    _save(db)
    return record


def get_all_artifacts() -> list:
    db = _load()
    return list(db["artifacts"].values())


def get_artifacts_by_ids(artifact_ids: list) -> list:
    db = _load()
    return [db["artifacts"][aid] for aid in artifact_ids if aid in db["artifacts"]]


def get_artifact(artifact_id: str) -> Optional[dict]:
    db = _load()
    return db["artifacts"].get(artifact_id)


# --- versions ---

def insert_version(record: dict) -> dict:
    db = _load()
    db["versions"][record["version_id"]] = record
    _save(db)
    _ensure_version_dir(record["project_id"], record["version_id"])
    return record


def get_all_versions() -> list:
    db = _load()
    return list(db["versions"].values())


def get_version(version_id: str) -> Optional[dict]:
    db = _load()
    return db["versions"].get(version_id)


# --- reviews ---

def insert_review(record: dict) -> dict:
    db = _load()
    db["reviews"][record["review_id"]] = record
    _save(db)
    _ensure_review_dir(record["project_id"], record["version_id"], record["review_id"])
    return record


def get_all_reviews() -> list:
    db = _load()
    return list(db["reviews"].values())


def get_review(review_id: str) -> Optional[dict]:
    db = _load()
    return db["reviews"].get(review_id)


# --- filesystem helpers ---

def _ensure_version_dir(project_id: str, version_id: str) -> None:
    """Create /storage/projects/{project_id}/versions/{version_id}/reviews/ on disk."""
    path = _version_reviews_path(project_id, version_id)
    os.makedirs(path, exist_ok=True)


def _ensure_review_dir(project_id: str, version_id: str, review_id: str) -> None:
    """Create review output directory and write empty placeholder JSON."""
    base = _version_reviews_path(project_id, version_id)
    review_dir = os.path.join(base, review_id)
    os.makedirs(review_dir, exist_ok=True)
    output_file = os.path.join(review_dir, "review_output.json")
    if not os.path.exists(output_file):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _version_reviews_path(project_id: str, version_id: str) -> str:
    storage_root = os.path.dirname(__file__)
    return os.path.join(storage_root, "projects", project_id, "versions", version_id, "reviews")
