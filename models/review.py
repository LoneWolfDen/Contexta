import uuid
from datetime import datetime, timezone


def make_review(
    version_id: str,
    project_id: str,
    result: dict = None,
    config: dict = None,
    personas: list = None,
    prompt_context: dict = None,
) -> dict:
    """
    Create a review record linked to a version.

    result shape (produced by review_analysis_service):
    {
        "summary":        {overall_assessment, key_findings, recommended_focus},
        "weaknesses":     [{weakness_id, category, severity, description, source_refs}],
        "explainability": {based_on, rules_used},
        "prompt_context": {base_prompt, persona_prompts, user_context, version_context_refs},
        "personas":       [str, ...],
    }
    """
    full_result = result or {
        "summary": {
            "overall_assessment": "",
            "key_findings": [],
            "recommended_focus": [],
        },
        "weaknesses": [],
        "explainability": {
            "based_on": [],
            "rules_used": [],
        },
    }

    # Attach persona and prompt_context directly onto result so they are
    # visible in the top-level result block returned to callers.
    full_result["personas"] = personas if personas is not None else []
    full_result["prompt_context"] = prompt_context or {
        "base_prompt": "",
        "persona_prompts": [],
        "user_context": "",
        "version_context_refs": ["version_summary", "artifact_snapshot"],
    }

    return {
        "review_id": str(uuid.uuid4()),
        "version_id": version_id,
        "project_id": project_id,
        "status": "complete",
        "result": full_result,
        "config": config or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
