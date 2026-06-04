"""
Review Service
Responsibility: validate version exists, run deterministic review analysis, persist result.
Input  → version_id, optional personas, user_context, config
Process → verify version exists, build prompt_context, call review_analysis_service,
          attach prompt_context + personas to result, build and store review record
Output → stored review dict
"""

from models.review import make_review
from services.prompt_builder_service import build_prompt_context, resolve_personas
from services.review_analysis_service import generate_review
from storage import store


def create_review(payload: dict) -> dict:
    """Run a deterministic review against a version and persist the result."""
    _validate(payload)

    version_id = payload["version_id"]
    version = store.get_version(version_id)
    if version is None:
        raise ValueError(f"version_id '{version_id}' does not exist.")

    personas = resolve_personas(payload.get("personas") or [])
    prompt_context = build_prompt_context(version, payload)
    result = generate_review(version, personas=personas)

    record = make_review(
        version_id=version_id,
        project_id=version["project_id"],
        result=result,
        config=payload.get("config", {}),
        personas=personas,
        prompt_context=prompt_context,
    )
    return store.insert_review(record)


def list_reviews() -> list:
    """Return all stored reviews."""
    return store.get_all_reviews()


def _validate(payload: dict) -> None:
    if not payload.get("version_id"):
        raise ValueError("Missing required field: version_id")
