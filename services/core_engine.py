"""
Core Engine — Hub
Responsibility: orchestrate the locked workflow.
  Ingest → Version → Review

This module coordinates calls between services.
It does NOT contain business logic — each service owns its own logic.
"""

from services import ingestion_service, version_service, review_service


def run_ingestion(payload: dict) -> dict:
    """Entry point: ingest an artifact."""
    return ingestion_service.ingest_artifact(payload)


def run_version(payload: dict) -> dict:
    """Entry point: create a version from selected artifacts."""
    return version_service.create_version(payload)


def run_review(payload: dict) -> dict:
    """Entry point: run a review against a version."""
    return review_service.create_review(payload)
