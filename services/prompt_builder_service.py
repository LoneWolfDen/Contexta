"""
Prompt Builder Service
Responsibility: build a structured prompt_context from version data and review payload.
Input  → version dict, payload dict
Process → derive base_prompt, persona_prompts, user_context, version_context_refs
Output → prompt_context dict

Rules:
- No AI calls.
- No free-form text generation beyond simple structured strings.
- Deterministic: same inputs always produce same output.
- Persona handlers are isolated and extensible.
"""

# ---------------------------------------------------------------------------
# Supported personas and their deterministic configurations
# ---------------------------------------------------------------------------

_PERSONA_CONFIG = {
    "architect": {
        "label": "Architect",
        "focus": "architecture and design gaps",
        "priority_categories": ["architecture_understanding", "solution_understanding"],
        "prompt_directive": "Prioritise architecture and design gaps in the review output.",
    },
    "delivery lead": {
        "label": "Delivery Lead",
        "focus": "delivery model and dependencies",
        "priority_categories": ["delivery_model", "dependencies"],
        "prompt_directive": "Prioritise delivery model and dependency gaps in the review output.",
    },
    "security": {
        "label": "Security",
        "focus": "security-related context",
        "priority_categories": ["constraints"],
        "prompt_directive": "Flag missing security-related context if not present in version summary.",
    },
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_prompt_context(version: dict, payload: dict) -> dict:
    """
    Build a structured prompt_context dict.

    Args:
        version: version record (contains version_summary, artifact_snapshot)
        payload: review request payload (may contain personas, user_context)

    Returns:
        {
            "base_prompt": str,
            "persona_prompts": list[dict],
            "user_context": str,
            "version_context_refs": list[str],
        }
    """
    personas = _normalise_personas(payload.get("personas") or [])
    user_context = payload.get("user_context") or ""

    base_prompt = _build_base_prompt(version)
    persona_prompts = [_build_persona_prompt(p) for p in personas]
    version_context_refs = _build_version_context_refs(version)

    return {
        "base_prompt": base_prompt,
        "persona_prompts": persona_prompts,
        "user_context": user_context,
        "version_context_refs": version_context_refs,
    }


# ---------------------------------------------------------------------------
# Persona resolution helpers
# ---------------------------------------------------------------------------

def resolve_personas(personas: list) -> list:
    """
    Return a deduplicated list of normalised, recognised persona keys.
    Unrecognised persona strings are silently dropped.
    """
    return _normalise_personas(personas)


def _normalise_personas(personas: list) -> list:
    """Lowercase and deduplicate, keeping only known persona keys."""
    seen = []
    for p in personas:
        key = p.strip().lower()
        if key in _PERSONA_CONFIG and key not in seen:
            seen.append(key)
    return seen


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_base_prompt(version: dict) -> str:
    """Produce a minimal base prompt string from the version record."""
    version_id = version.get("version_id", "unknown")
    return f"Review version {version_id} using available version summary and artifact snapshot."


def _build_persona_prompt(persona_key: str) -> dict:
    """Build one persona prompt entry from the persona config."""
    cfg = _PERSONA_CONFIG[persona_key]
    return {
        "persona": cfg["label"],
        "focus": cfg["focus"],
        "directive": cfg["prompt_directive"],
    }


def _build_version_context_refs(version: dict) -> list:
    """
    Return which context blocks are available in this version.
    Always includes the two canonical refs; presence is structural, not conditional.
    """
    refs = []
    if version.get("version_summary") is not None:
        refs.append("version_summary")
    if version.get("artifact_snapshot") is not None:
        refs.append("artifact_snapshot")
    # Guarantee both are present even when keys are missing
    for ref in ("version_summary", "artifact_snapshot"):
        if ref not in refs:
            refs.append(ref)
    return refs
