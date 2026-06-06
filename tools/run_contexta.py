import json
import os
import textwrap
from pathlib import Path
from datetime import datetime

import requests

BASE_URL = os.getenv("CONTEXTA_BASE_URL", "http://localhost:5000")
RUNS_DIR = Path("tools/contexta_runs")
RUNS_FILE = RUNS_DIR / "runs.json"

RUNS_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Helpers
# =========================================================

def now():
    return datetime.utcnow().isoformat() + "Z"


def hr(char="=", width=80):
    print(char * width)


def title(text):
    print()
    hr("=")
    print(text)
    hr("=")


def section(text):
    print()
    hr("-")
    print(text)
    hr("-")


def ok(text):
    print(f"✅ {text}")


def warn(text):
    print(f"⚠️  {text}")


def err(text):
    print(f"❌ {text}")


def pretty(obj):
    print(json.dumps(obj, indent=2))


def first_sentence(text):
    if not text:
        return ""
    parts = str(text).split(".")
    first = parts[0].strip()
    return first + ("." if first else "")


def friendly_category(cat):
    if not cat:
        return "Other"
    if "missing_information" in cat:
        return "Missing key inputs"
    if "missing_security_context" in cat:
        return "Security gaps"
    return cat.replace("_", " ").title()


def load_runs():
    if not RUNS_FILE.exists():
        return []
    with open(RUNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_runs(runs):
    with open(RUNS_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2)


def append_run(record):
    runs = load_runs()
    runs.append(record)
    save_runs(runs)


def choose_from_list(items, label_getter):
    if not items:
        warn("No items available.")
        return None

    for idx, item in enumerate(items, start=1):
        label = label_getter(item)
        print(f"{idx}. {label}")

    choice = input("Select option: ").strip()
    if not choice.isdigit():
        return None

    idx = int(choice) - 1
    if idx < 0 or idx >= len(items):
        return None

    return items[idx]


def side_by_side(left_title, left_text, right_title, right_text, width=48):
    left_lines = textwrap.wrap(left_text or "", width=width)
    right_lines = textwrap.wrap(right_text or "", width=width)

    max_len = max(len(left_lines), len(right_lines), 1)

    print()
    print(f"{left_title:<{width}} | {right_title:<{width}}")
    print(f"{'-' * width} | {'-' * width}")

    for i in range(max_len):
        l = left_lines[i] if i < len(left_lines) else ""
        r = right_lines[i] if i < len(right_lines) else ""
        print(f"{l:<{width}} | {r:<{width}}")


# =========================================================
# API helpers
# =========================================================

def api_post(path, payload):
    res = requests.post(f"{BASE_URL}{path}", json=payload)
    if not res.ok:
        raise RuntimeError(f"POST {path} failed: {res.status_code} {res.text}")
    return res.json()


def api_get(path):
    res = requests.get(f"{BASE_URL}{path}")
    if not res.ok:
        raise RuntimeError(f"GET {path} failed: {res.status_code} {res.text}")
    return res.json()


# =========================================================
# Core API flows
# =========================================================

def create_project():
    name = input("Project name: ").strip()
    data = api_post("/projects", {"name": name})
    ok(f"Project created: {data['project_id']}")
    return data


def create_artifact(project_id, file_path, artifact_type="document", source_type="upload"):
    payload = {
        "project_id": project_id,
        "type": artifact_type,
        "source_type": source_type,
        "file_path": file_path
    }
    data = api_post("/artifacts", payload)
    ok(f"Artifact created: {data['artifact_id']} ({file_path})")
    return data


def create_version(project_id, artifact_ids):
    payload = {
        "project_id": project_id,
        "artifact_ids": artifact_ids
    }
    data = api_post("/versions", payload)
    ok(f"Version created: {data['version_id']}")
    return data


def create_review(version_id, personas=None, user_context=""):
    payload = {"version_id": version_id}
    if personas:
        payload["personas"] = personas
    if user_context:
        payload["user_context"] = user_context

    data = api_post("/reviews", payload)
    ok(f"Review created: {data['review_id']}")
    return data


def create_reconciliation(review_ids):
    data = api_post("/reconciliation", {"review_ids": review_ids})
    ok(f"Reconciliation created: {data['recon_id']}")
    return data


def create_proposal_from_recon(recon_id):
    data = api_post("/proposal", {"recon_id": recon_id})
    ok(f"Proposal created: {data['proposal_id']}")
    return data


def create_learning(source_type, source_id):
    data = api_post("/learning", {"source_type": source_type, "source_id": source_id})
    ok(f"Learning created: {data['learning_id']}")
    return data


# =========================================================
# Groq hook (CLI-only, optional)
# =========================================================

def call_groq(prompt, model=None):
    """
    Optional hook.
    Requires:
      export GROQ_API_KEY=...
      export GROQ_MODEL=...
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = model or os.getenv("GROQ_MODEL", "").strip()

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    if not model:
        raise RuntimeError("GROQ_MODEL is not set.")

    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise proposal refinement assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    res = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if not res.ok:
        raise RuntimeError(f"Groq request failed: {res.status_code} {res.text}")

    data = res.json()
    return data["choices"][0]["message"]["content"]


def enhance_proposal_with_groq():
    title("Groq Enhancement Hook")

    runs = load_runs()
    proposal_runs = [r for r in runs if r.get("proposal")]
    if not proposal_runs:
        warn("No saved runs with proposals found.")
        return

    selected = choose_from_list(
        proposal_runs,
        lambda r: f"{r.get('label', '(no label)')} | proposal={r.get('proposal', {}).get('proposal_id', '')}"
    )

    if not selected:
        warn("No valid run selected.")
        return

    proposal = selected["proposal"]

    prompt = f"""
You are improving a structured proposal for readability.
Keep the meaning intact.
Return only concise improved text.

Executive Summary:
{proposal.get("summary", {}).get("executive_summary", "")}

Problem Statement:
{proposal.get("summary", {}).get("problem_statement", "")}

Recommended Solution:
{proposal.get("summary", {}).get("recommended_solution", "")}
""".strip()

    try:
        groq_output = call_groq(prompt)
        section("Groq Enhanced Output")
        print(groq_output)

        section("Side-by-side")
        side_by_side(
            "Original Executive Summary",
            proposal.get("summary", {}).get("executive_summary", ""),
            "Groq Enhanced",
            groq_output
        )

    except Exception as exc:
        err(str(exc))


# =========================================================
# Comparison helpers
# =========================================================

def summarize_review(review):
    result = review.get("result", {})
    weaknesses = result.get("weaknesses", [])
    summary = result.get("summary", {})

    categories = {}
    severities = {"high": 0, "medium": 0, "low": 0}

    for w in weaknesses:
        cat = w.get("category", "unknown")
        sev = str(w.get("severity", "low")).lower()
        categories[cat] = categories.get(cat, 0) + 1
        if sev in severities:
            severities[sev] += 1

    return {
        "review_id": review.get("review_id"),
        "personas": result.get("personas", []),
        "overall_assessment": summary.get("overall_assessment", ""),
        "weakness_count": len(weaknesses),
        "categories": categories,
        "severities": severities,
        "recommended_focus": summary.get("recommended_focus", [])
    }


def compare_reviews(review_a, review_b):
    a = summarize_review(review_a)
    b = summarize_review(review_b)

    title("Review Comparison")

    print(f"A review_id: {a['review_id']}")
    print(f"B review_id: {b['review_id']}")
    print(f"A personas: {a['personas']}")
    print(f"B personas: {b['personas']}")

    side_by_side(
        "A overall assessment",
        a["overall_assessment"],
        "B overall assessment",
        b["overall_assessment"]
    )

    section("Weakness Counts")
    print(f"A weakness count: {a['weakness_count']}")
    print(f"B weakness count: {b['weakness_count']}")

    section("Category Counts")
    print("A:")
    pretty(a["categories"])
    print("B:")
    pretty(b["categories"])

    section("Severity Counts")
    print("A:")
    pretty(a["severities"])
    print("B:")
    pretty(b["severities"])

    section("Recommended Focus")
    print("A:")
    pretty(a["recommended_focus"])
    print("B:")
    pretty(b["recommended_focus"])


def compare_proposals(proposal_a, proposal_b):
    title("Proposal Comparison")

    print(f"A proposal_id: {proposal_a.get('proposal_id')}")
    print(f"B proposal_id: {proposal_b.get('proposal_id')}")

    side_by_side(
        "A executive summary",
        proposal_a.get("summary", {}).get("executive_summary", ""),
        "B executive summary",
        proposal_b.get("summary", {}).get("executive_summary", "")
    )

    side_by_side(
        "A recommended solution",
        proposal_a.get("summary", {}).get("recommended_solution", ""),
        "B recommended solution",
        proposal_b.get("summary", {}).get("recommended_solution", "")
    )

    section("A recommendations")
    pretty(proposal_a.get("recommendations", []))

    section("B recommendations")
    pretty(proposal_b.get("recommendations", []))


# =========================================================
# Saved runs
# =========================================================

def save_pipeline_run(project, artifacts, version, reviews, reconciliation=None, proposal=None, learning=None, label=""):
    record = {
        "saved_at": now(),
        "label": label or version.get("version_id"),
        "project": project,
        "artifacts": artifacts,
        "version": version,
        "reviews": reviews,
        "reconciliation": reconciliation,
        "proposal": proposal,
        "learning": learning
    }
    append_run(record)
    ok("Run saved locally.")
    return record


def show_saved_runs():
    title("Saved Runs")
    runs = load_runs()
    if not runs:
        warn("No saved runs found.")
        return

    for idx, run in enumerate(runs, start=1):
        label = run.get("label", "(no label)")
        saved_at = run.get("saved_at", "")
        version_id = run.get("version", {}).get("version_id", "")
        proposal_id = run.get("proposal", {}).get("proposal_id", "") if run.get("proposal") else ""
        print(f"{idx}. {label}")
        print(f"   saved_at: {saved_at}")
        print(f"   version:  {version_id}")
        print(f"   proposal: {proposal_id}")
        print()


# =========================================================
# Main pipeline flows
# =========================================================

def run_full_pipeline():
    title("Run Full Pipeline")

    project = create_project()

    section("Artifacts")
    paths = []
    while True:
        file_path = input("Artifact path (blank to finish, e.g. /files/sow.txt): ").strip()
        if not file_path:
            break
        paths.append(file_path)

    if not paths:
        warn("No artifact paths provided. Using defaults.")
        paths = ["/files/sow.txt", "/files/architecture.txt"]

    artifacts = [create_artifact(project["project_id"], p) for p in paths]
    artifact_ids = [a["artifact_id"] for a in artifacts]

    section("Version")
    version = create_version(project["project_id"], artifact_ids)

    section("Baseline Review")
    baseline_review = create_review(version["version_id"])

    section("Iteration-style Review")
    personas_input = input("Personas (comma-separated, e.g. Architect,Security) or blank: ").strip()
    personas = [p.strip() for p in personas_input.split(",") if p.strip()] if personas_input else ["Architect", "Security"]

    user_context = input("User context (optional, blank for default): ").strip()
    if not user_context:
        user_context = "Focus on architecture and security risks."

    iter_review = create_review(version["version_id"], personas=personas, user_context=user_context)

    section("Reconciliation")
    reconciliation = create_reconciliation([baseline_review["review_id"], iter_review["review_id"]])

    section("Proposal")
    proposal = create_proposal_from_recon(reconciliation["recon_id"])
    pretty(proposal)

    section("Learning")
    learning = create_learning("proposal", proposal["proposal_id"])
    pretty(learning)

    save_pipeline_run(
        project=project,
        artifacts=artifacts,
        version=version,
        reviews=[baseline_review, iter_review],
        reconciliation=reconciliation,
        proposal=proposal,
        learning=learning,
        label=project["name"]
    )


def run_iteration_only():
    title("Run Iteration-style Review on Existing Version")

    versions = api_get("/versions")
    selected = choose_from_list(
        versions,
        lambda v: f"{v.get('version_id')} | project={v.get('project_id')}"
    )
    if not selected:
        warn("No valid version selected.")
        return

    personas_input = input("Personas (comma-separated, e.g. Architect,Delivery Lead,Security): ").strip()
    personas = [p.strip() for p in personas_input.split(",") if p.strip()] if personas_input else []

    user_context = input("User context (optional): ").strip()

    review = create_review(selected["version_id"], personas=personas, user_context=user_context)

    section("Review Output")
    pretty(review)


def compare_two_reviews_from_api():
    title("Compare Two Existing Reviews")

    reviews = api_get("/reviews")
    if len(reviews) < 2:
        warn("Need at least two reviews.")
        return

    print("Select Review A")
    review_a = choose_from_list(reviews, lambda r: r.get("review_id", ""))
    if not review_a:
        warn("Invalid selection.")
        return

    print("\nSelect Review B")
    review_b = choose_from_list(reviews, lambda r: r.get("review_id", ""))
    if not review_b:
        warn("Invalid selection.")
        return

    compare_views = input("Compare type: [1] Full details  [2] Side-by-side summary only: ").strip()
    if compare_views == "2":
        a = summarize_review(review_a)
        b = summarize_review(review_b)
        side_by_side(
            "Review A",
            a["overall_assessment"],
            "Review B",
            b["overall_assessment"]
        )
    else:
        compare_reviews(review_a, review_b)


def compare_two_saved_proposals():
    title("Compare Two Saved Proposals")
    runs = load_runs()
    proposal_runs = [r for r in runs if r.get("proposal")]
    if len(proposal_runs) < 2:
        warn("Need at least two saved runs with proposals.")
        return

    print("Select Proposal Run A")
    run_a = choose_from_list(
        proposal_runs,
        lambda r: f"{r.get('label', '(no label)')} | proposal={r.get('proposal', {}).get('proposal_id', '')}"
    )
    if not run_a:
        warn("Invalid selection.")
        return

    print("\nSelect Proposal Run B")
    run_b = choose_from_list(
        proposal_runs,
        lambda r: f"{r.get('label', '(no label)')} | proposal={r.get('proposal', {}).get('proposal_id', '')}"
    )
    if not run_b:
        warn("Invalid selection.")
        return

    compare_proposals(run_a["proposal"], run_b["proposal"])


# =========================================================
# Menu
# =========================================================

def main():
    while True:
        title("Contexta CLI v3")

        print("1. Run Full Pipeline")
        print("2. Run Iteration-style Review on Existing Version")
        print("3. Compare Two Existing Reviews")
        print("4. Compare Two Saved Proposals")
        print("5. Show Saved Runs")
        print("6. Groq Enhancement Hook (Proposal)")
        print("7. Exit")

        choice = input("\nSelect option: ").strip()

        try:
            if choice == "1":
                run_full_pipeline()
            elif choice == "2":
                run_iteration_only()
            elif choice == "3":
                compare_two_reviews_from_api()
            elif choice == "4":
                compare_two_saved_proposals()
            elif choice == "5":
                show_saved_runs()
            elif choice == "6":
                enhance_proposal_with_groq()
            elif choice == "7":
                print("Exiting.")
                break
            else:
                warn("Invalid option")
        except Exception as exc:
            err(str(exc))


if __name__ == "__main__":
    main()
