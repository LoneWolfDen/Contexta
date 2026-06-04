"""
Version Summary Service
Responsibility: derive a structured summary from an artifact snapshot.
Input  → snapshot: list of artifact dicts
Process → deterministic extraction from file_path and type fields only
Output → version_summary dict

Rules:
- No AI calls.
- No assumptions. Missing data → recorded in missing_information.
- All fields always present in output (empty string or empty list).
"""

SUMMARY_FIELDS = (
    "client_ask",
    "solution_understanding",
    "technology_landscape",
    "delivery_model",
    "tooling_recommendations",
    "constraints",
    "dependencies",
    "architecture_understanding",
    "missing_information",
)

# Artifact types that signal each summary section
_TYPE_SIGNALS = {
    "client_ask":              {"brief", "requirement", "rfp", "statement_of_work", "sow"},
    "solution_understanding":  {"solution", "design", "proposal", "scope"},
    "technology_landscape":    {"technology", "tech", "stack", "infrastructure", "platform"},
    "delivery_model":          {"delivery", "plan", "roadmap", "timeline", "schedule"},
    "tooling_recommendations": {"tool", "tooling", "software", "application"},
    "constraints":             {"constraint", "sla", "kpi", "geography", "compliance"},
    "dependencies":            {"dependency", "integration", "interface", "api"},
    "architecture_understanding": {"architecture", "diagram", "drawio", "component", "system"},
}

# Fields whose expected value is a list
_LIST_FIELDS = {"constraints", "dependencies", "missing_information"}

# Sections that MUST have at least one matching artifact — absence → missing_information
_REQUIRED_SECTIONS = {
    "client_ask",
    "solution_understanding",
    "architecture_understanding",
}


def generate_version_summary(snapshot: list) -> dict:
    """
    Derive a structured version summary from an artifact snapshot.

    Extraction is purely deterministic:
    - artifact.type and artifact.file_path tokens are matched against known signals.
    - If a required section has no matching artifact it is added to missing_information.
    - All nine keys are always present.
    """
    summary = _empty_summary()

    for artifact in snapshot:
        _apply_artifact(summary, artifact)

    _flag_missing(summary)

    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_summary() -> dict:
    """Return a summary dict with all fields initialised to safe empty values."""
    return {
        "client_ask": "",
        "solution_understanding": "",
        "technology_landscape": "",
        "delivery_model": "",
        "tooling_recommendations": "",
        "constraints": [],
        "dependencies": [],
        "architecture_understanding": "",
        "missing_information": [],
    }


def _apply_artifact(summary: dict, artifact: dict) -> None:
    """Fill summary fields using signals found in one artifact."""
    tokens = _tokens(artifact)

    for field, signals in _TYPE_SIGNALS.items():
        if not tokens & signals:
            continue

        label = _artifact_label(artifact)

        if field in _LIST_FIELDS:
            if label not in summary[field]:
                summary[field].append(label)
        else:
            if not summary[field]:
                summary[field] = label


def _flag_missing(summary: dict) -> None:
    """Add a note to missing_information for each required section that is empty."""
    for section in _REQUIRED_SECTIONS:
        value = summary[section]
        is_empty = (value == "") if section not in _LIST_FIELDS else (len(value) == 0)
        if is_empty:
            note = f"No artifact found covering '{section}'"
            if note not in summary["missing_information"]:
                summary["missing_information"].append(note)


def _tokens(artifact: dict) -> set:
    """
    Extract lower-case word tokens from artifact type and file_path.
    Splits on common path separators and underscores so
    '/files/architecture_diagram.pdf' yields {'files','architecture','diagram','pdf'}.
    """
    raw = f"{artifact.get('type', '')} {artifact.get('file_path', '')}"
    # normalise separators then split
    normalised = raw.replace("/", " ").replace("\\", " ").replace("_", " ").replace("-", " ").replace(".", " ")
    return {t.lower() for t in normalised.split() if t}


def _artifact_label(artifact: dict) -> str:
    """Return a short human-readable label for an artifact."""
    file_path = artifact.get("file_path", "")
    artifact_type = artifact.get("type", "artifact")
    name = file_path.split("/")[-1] if file_path else ""
    return f"{artifact_type}: {name}" if name else artifact_type
