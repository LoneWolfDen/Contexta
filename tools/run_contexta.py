import json
import os
from pathlib import Path
from datetime import datetime
import requests

BASE_URL = "http://localhost:5000"
RUNS_DIR = Path("tools/contexta_runs")
RUNS_FILE = RUNS_DIR / "runs.json"

RUNS_DIR.mkdir(parents=True, exist_ok=True)


def now():
    return datetime.utcnow().isoformat() + "Z"


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


def pretty(obj):
    print(json.dumps(obj, indent=2))


def choose_from_list(items, label_field="id"):
    if not items:
        print("No items available.")
        return None
    for idx, item in enumerate(items, start=1):
        label = item.get(label_field) if isinstance(item, dict) else str(item)
        print(f"{idx}. {label}")
    choice = input("Select option: ").strip()
    if not choice.isdigit():
        return None
    idx = int(choice) - 1
    if idx < 0 or idx >= len(items):
        return None
    return items[idx]


# ---------------------------
# API helpers
# ---------------------------

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


# ---------------------------
# Core pipeline steps
# ---------------------------

def create_project():
    name = input("Project name: ").strip()
    data = api_post("/projects", {"name": name})
    print(f"✅ Project created: {data['project_id']}")
    return data


def create_artifact(project_id, file_path, artifact_type="document", source_type="upload"):
    payload = {
        "project_id": project_id,
        "type": artifact_type,
        "source_type": source_type,
        "file_path": file_path
    }
    data = api_post("/artifacts", payload)
    print(f"✅ Artifact created: {data['artifact_id']} ({file_path})")
    return data


def create_version(project_id, artifact_ids):
    payload = {
        "project_id": project_id,
        "artifact_ids": artifact_ids
    }
    data = api_post("/versions", payload)
    print(f"✅ Version created: {data['version_id']}")
    return data


def create_review(version_id, personas=None, user_context=""):
    payload = {
        "version_id": version_id
    }
    if personas:
        payload["personas"] = personas
    if user_context:
        payload["user_context"] = user_context

    data = api_post("/reviews", payload)
    print(f"✅ Review created: {data['review_id']}")
    return data


def create_reconciliation(review_ids):
    payload = {"review_ids": review_ids}
    data = api_post("/reconciliation", payload)
    print(f"✅ Reconciliation created: {data['recon_id']}")
    return data


def create_proposal_from_recon(recon_id):
    payload = {"recon_id": recon_id}
    data = api_post("/proposal", payload)
    print(f"✅ Proposal created: {data['proposal_id']}")
    return data


def create_learning(source_type, source_id):
    payload = {"source_type": source_type, "source_id": source_id}
    data = api_post("/learning", payload)
    print(f"✅ Learning created: {data['learning_id']}")
    return data


# ---------------------------
# Comparison helpers
# ---------------------------

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

    print("\n=== REVIEW COMPARISON ===")
    print(f"A review_id: {a['review_id']}")
    print(f"B review_id: {b['review_id']}")
    print(f"A personas: {a['personas']}")
    print(f"B personas: {b['personas']}")
    print()
    print("A overall assessment:")
    print(a["overall_assessment"])
    print()
    print("B overall assessment:")
    print(b["overall_assessment"])
    print()
    print(f"A weakness count: {a['weakness_count']}")
    print(f"B weakness count: {b['weakness_count']}")
    print()
    print("A category counts:")
    pretty(a["categories"])
    print("B category counts:")
    pretty(b["categories"])
    print()
    print("A severities:")
    pretty(a["severities"])
    print("B severities:")
    pretty(b["severities"])
    print()
    print("A recommended focus:")
    pretty(a["recommended_focus"])
    print("B recommended focus:")
    pretty(b["recommended_focus"])


def compare_proposals(proposal_a, proposal_b):
    print("\n=== PROPOSAL COMPARISON ===")
    print(f"A proposal_id: {proposal_a.get('proposal_id')}")
    print(f"B proposal_id: {proposal_b.get('proposal_id')}")
    print()
    print("A executive summary:")
    print(proposal_a.get("summary", {}).get("executive_summary", ""))
    print()
    print("B executive summary:")
    print(proposal_b.get("summary", {}).get("executive_summary", ""))
    print()
    print("A recommendations:")
    pretty(proposal_a.get("recommendations", []))
    print("B recommendations:")
    pretty(proposal_b.get("recommendations", []))


# ---------------------------
# Saved run helpers
# ---------------------------

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
    print("✅ Run saved locally.")
    return record


def show_saved_runs():
    runs = load_runs()
    if not runs:
        print("No saved runs found.")
        return
    print("\n=== SAVED RUNS ===")
    for idx, run in enumerate(runs, start=1):
        label = run.get("label", "(no label)")
        saved_at = run.get("saved_at", "")
        version_id = run.get("version", {}).get("version_id", "")
        print(f"{idx}. {label} | version={version_id} | saved_at={saved_at}")


# ---------------------------
# Pipeline flows
# ---------------------------

def run_full_pipeline():
    print("\n--- Running Full Pipeline ---")

    project = create_project()

    print("\nAdd artifacts for this run.")
    paths = []
    while True:
        file_path = input("Artifact path (or blank to finish, e.g. /files/sow.txt): ").strip()
        if not file_path:
            break
        paths.append(file_path)

    if not paths:
        print("No artifact paths provided. Using defaults.")
        paths = ["/files/sow.txt", "/files/architecture.txt"]

    artifacts = [create_artifact(project["project_id"], p) for p in paths]
    artifact_ids = [a["artifact_id"] for a in artifacts]

    version = create_version(project["project_id"], artifact_ids)

    print("\nCreating baseline review...")
    baseline_review = create_review(version["version_id"])

    print("\nCreating iteration-style review...")
    personas_input = input("Personas (comma-separated, e.g. Architect,Security) or blank: ").strip()
    personas = [p.strip() for p in personas_input.split(",") if p.strip()] if personas_input else ["Architect", "Security"]
    user_context = input("User context (optional, blank for default): ").strip()
    if not user_context:
        user_context = "Focus on architecture and security risks."

    iter_review = create_review(version["version_id"], personas=personas, user_context=user_context)

    reconciliation = create_reconciliation([baseline_review["review_id"], iter_review["review_id"]])
    proposal = create_proposal_from_recon(reconciliation["recon_id"])
    learning = create_learning("proposal", proposal["proposal_id"])

    print("\n✅ Final Proposal Output:")
    pretty(proposal)

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
    print("\n--- Run iteration-style review on existing version ---")
    versions = api_get("/versions")
    selected = choose_from_list(versions, "version_id")
    if not selected:
        print("No valid version selected.")
        return

    personas_input = input("Personas (comma-separated, e.g. Architect,Delivery Lead,Security): ").strip()
    personas = [p.strip() for p in personas_input.split(",") if p.strip()] if personas_input else []
    user_context = input("User context (optional): ").strip()

    review = create_review(selected["version_id"], personas=personas, user_context=user_context)
    print("\n✅ Review Output:")
    pretty(review)


def compare_two_reviews_from_api():
    print("\n--- Compare two existing reviews ---")
    reviews = api_get("/reviews")
    if len(reviews) < 2:
        print("Need at least two reviews.")
        return

    print("\nSelect Review A")
    review_a = choose_from_list(reviews, "review_id")
    if not review_a:
        print("Invalid selection.")
        return

    print("\nSelect Review B")
    review_b = choose_from_list(reviews, "review_id")
    if not review_b:
        print("Invalid selection.")
        return

    compare_reviews(review_a, review_b)


def compare_two_saved_proposals():
    print("\n--- Compare two saved proposals ---")
    runs = load_runs()
    proposal_runs = [r for r in runs if r.get("proposal")]
    if len(proposal_runs) < 2:
        print("Need at least two saved runs with proposals.")
        return

    print("\nSelect Proposal Run A")
    run_a = choose_from_list(proposal_runs, "label")
    if not run_a:
        print("Invalid selection.")
        return

    print("\nSelect Proposal Run B")
    run_b = choose_from_list(proposal_runs, "label")
    if not run_b:
        print("Invalid selection.")
        return

    compare_proposals(run_a["proposal"], run_b["proposal"])


# ---------------------------
# Main menu
# ---------------------------

def main():
    while True:
        print("\n=== Contexta CLI v2 ===")
        print("1. Run Full Pipeline")
        print("2. Run Iteration-style Review on Existing Version")
        print("3. Compare Two Existing Reviews")
        print("4. Compare Two Saved Proposals")
        print("5. Show Saved Runs")
        print("6. Exit")

        choice = input("Select option: ").strip()

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
                print("Exiting.")
                break
            else:
                print("Invalid option")
        except Exception as exc:
            print(f"\n❌ Error: {exc}")


if __name__ == "__main__":
    main()