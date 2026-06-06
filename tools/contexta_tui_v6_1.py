from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static, Input, Button, Label
from textual.containers import Horizontal, Vertical

import requests
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:5000"

ALIASES_DIR = Path("tools/contexta_runs")
ALIASES_FILE = ALIASES_DIR / "aliases.json"
ALIASES_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# API helpers
# =========================================================

def api_get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}")
        return r.json() if r.ok else []
    except Exception:
        return []


def api_post(path, payload):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=payload)
        return r.json() if r.ok else None
    except Exception:
        return None


# =========================================================
# Alias / naming helpers
# =========================================================

def load_aliases():
    if not ALIASES_FILE.exists():
        return {}
    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_aliases(data):
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def timestamp_label():
    return datetime.now().strftime("%d%m%y_%H%M%S")


def ensure_alias(obj_type: str, obj_id: str):
    aliases = load_aliases()
    key = f"{obj_type}:{obj_id}"

    if key not in aliases:
        existing = [k for k in aliases.keys() if k.startswith(f"{obj_type}:")]
        sequence = len(existing) + 1
        aliases[key] = f"{obj_type.capitalize()}_{timestamp_label()}_{sequence:02d}"
        save_aliases(aliases)

    return aliases[key]


# =========================================================
# Friendly labels
# =========================================================

def friendly_category(cat: str) -> str:
    if not cat:
        return "Other"
    if "missing_information" in cat:
        return "Missing key inputs"
    if "missing_security_context" in cat:
        return "Security gaps"
    return cat.replace("_", " ").title()


def first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = str(text).split(".")
    first = parts[0].strip()
    return first + ("." if first else "")


# =========================================================
# Main App
# =========================================================

class ContextaOperatorConsole(App):

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #left_panel {
        width: 32%;
        border-right: solid #555;
    }

    #right_panel {
        width: 68%;
        padding: 0 1;
    }

    #top_right {
        height: 1fr;
    }

    #details_panel {
        width: 50%;
        border-right: solid #444;
        padding: 1;
    }

    #compare_learning_panel {
        width: 50%;
        padding: 1;
    }

    #compare_panel {
        height: 50%;
        border-bottom: solid #444;
        padding-bottom: 1;
    }

    #learning_panel {
        height: 50%;
        padding-top: 1;
    }

    #run_panel {
        height: 10;
        border-top: solid #666;
        padding: 1;
    }

    #action_row {
        height: auto;
    }

    Button {
        margin-right: 1;
    }

    Input {
        margin-bottom: 1;
    }

    .section_title {
        text-style: bold;
    }

    #log_panel {
        height: 3;
        border-top: solid #444;
        padding-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="body"):

            # LEFT: pipeline tree
            with Vertical(id="left_panel"):
                yield Static("Pipeline Explorer", classes="section_title")
                yield Tree("Contexta Pipeline", id="pipeline_tree")

            # RIGHT: details + compare/learning + run controls + logs
            with Vertical(id="right_panel"):

                with Horizontal(id="top_right"):

                    with Vertical(id="details_panel"):
                        yield Static("Details", classes="section_title")
                        yield Static("Select a node from the tree", id="details_output")

                    with Vertical(id="compare_learning_panel"):

                        with Vertical(id="compare_panel"):
                            yield Static("Compare", classes="section_title")
                            yield Static("Press Compare, then select A and B nodes", id="compare_output")

                        with Vertical(id="learning_panel"):
                            yield Static("Learning", classes="section_title")
                            yield Static("Select a learning node to inspect insights", id="learning_output")

                with Vertical(id="run_panel"):
                    yield Static("Run Controls", classes="section_title")
                    yield Label("Selected Scope: None", id="selected_scope")
                    yield Label("Action Help: Select a Version to run Review / Iteration, a Reconciliation to run Proposal, a Proposal to run Learning.", id="action_help")
                    yield Input(placeholder="Personas (e.g. Architect,Security)", id="input_personas")
                    yield Input(placeholder="User context (optional)", id="input_context")

                    with Horizontal(id="action_row"):
                        yield Button("Run Review", id="btn_review")
                        yield Button("Run Iteration", id="btn_iteration")
                        yield Button("Run Reconcile", id="btn_reconcile")
                        yield Button("Run Proposal", id="btn_proposal")
                        yield Button("Run Learning", id="btn_learning")
                        yield Button("Compare Mode", id="btn_compare")
                        yield Button("Refresh", id="btn_refresh")

                with Vertical(id="log_panel"):
                    yield Static("Log", classes="section_title")
                    yield Static("Ready", id="log_output")

        yield Footer()

    # -----------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------

    def on_mount(self):
        self.pipeline_tree = self.query_one("#pipeline_tree", Tree)
        self.details_output = self.query_one("#details_output", Static)
        self.compare_output = self.query_one("#compare_output", Static)
        self.learning_output = self.query_one("#learning_output", Static)
        self.selected_scope = self.query_one("#selected_scope", Label)
        self.action_help = self.query_one("#action_help", Label)
        self.input_personas = self.query_one("#input_personas", Input)
        self.input_context = self.query_one("#input_context", Input)
        self.log_output = self.query_one("#log_output", Static)

        self.compare_mode = False
        self.compare_nodes = []

        self.load_tree()

    # -----------------------------------------------------
    # Logging
    # -----------------------------------------------------

    def ui_log(self, text: str):def ui_log
        self.log_output.update(text)

    # -----------------------------------------------------
    # Tree loading
    # -----------------------------------------------------

    def load_tree(self):
        root = self.pipeline_tree.root
        root.remove_children()
        root.label = "Contexta Pipeline"
        root.expand()

        projects = api_get("/projects")
        versions = api_get("/versions")
        reviews = api_get("/reviews")
        recons = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning_items = api_get("/learning")

        for project in projects:
            p_id = project.get("project_id", "")
            p_alias = ensure_alias("project", p_id)
            p_label = project.get("name") or p_alias

            p_node = root.add(
                f"📁 {p_label}",
                data=("project", project)
            )

            p_versions = [v for v in versions if v.get("project_id") == p_id]

            for version in p_versions:
                v_id = version.get("version_id", "")
                v_alias = ensure_alias("version", v_id)

                v_node = p_node.add(
                    f"📦 {v_alias}",
                    data=("version", version)
                )

                version_reviews = [r for r in reviews if r.get("version_id") == v_id]
                review_ids = [r.get("review_id") for r in version_reviews]

                reviews_group = v_node.add("📝 Reviews", None)

                for review in version_reviews:
                    r_id = review.get("review_id", "")
                    r_alias = ensure_alias("review", r_id)
                    personas = review.get("personas") or review.get("result", {}).get("personas", [])

                    label = r_alias
                    if personas:
                        label += f" [{', '.join(personas)}]"

                    reviews_group.add(
                        label,
                        data=("review", review)
                    )

                recon_group = v_node.add("🔗 Reconciliation", None)
                matched_recons = []

                for recon in recons:
                    ids = recon.get("review_ids") or recon.get("source_reviews") or []
                    if any(rid in ids for rid in review_ids):
                        matched_recons.append(recon)
                        recon_group.add(
                            ensure_alias("reconciliation", recon.get("recon_id", "")),
                            data=("reconciliation", recon)
                        )

                proposal_group = v_node.add("📄 Proposals", None)
                matched_props = []

                recon_ids = [r.get("recon_id") for r in matched_recons]

                for proposal in proposals:
                    if proposal.get("source_type") == "reconciliation" and proposal.get("source_id") in recon_ids:
                        matched_props.append(proposal)
                        proposal_group.add(
                            ensure_alias("proposal", proposal.get("proposal_id", "")),
                            data=("proposal", proposal)
                        )

                learning_group = v_node.add("📘 Learning", None)

                proposal_ids = [p.get("proposal_id") for p in matched_props]

                for learning in learning_items:
                    if learning.get("source_type") == "proposal" and learning.get("source_id") in proposal_ids:
                        learning_group.add(
                            ensure_alias("learning", learning.get("learning_id", "")),
                            data=("learning", learning)
                        )

        self.pipeline_tree.focus()

    # -----------------------------------------------------
    # Tree selection
    # -----------------------------------------------------

    def on_tree_node_selected(self, event):
        node = event.node

        if not node.data:
            return

        node_type, data = node.data
        self.update_selected_scope(node_type, data)

        if self.compare_mode and node_type in {"review", "proposal", "learning"}:
            self.compare_nodes.append((node_type, data))

            if len(self.compare_nodes) == 1:
                self.compare_output.update(f"A selected: {self.format_compare_label(node_type, data)}\nSelect second item...")
                self.ui_log("Compare mode: first item selected")
                return

            if len(self.compare_nodes) == 2:
                self.render_compare()
                self.compare_nodes = []
                self.compare_mode = False
                self.ui_log("Compare complete")
                return

        self.render_details(node_type, data)
        self.render_learning_panel(node_type, data)

    # -----------------------------------------------------
    # Scope / detail rendering
    # -----------------------------------------------------

    def update_selected_scope(self, node_type, data):
        label = self.format_compare_label(node_type, data)
        self.selected_scope.update(f"Selected Scope: {label}")

        if node_type == "version":
            self.action_help.update("Action Help: Run Review or Iteration on this Version. Reconcile can be used after at least two reviews exist.")
        elif node_type == "reconciliation":
            self.action_help.update("Action Help: Run Proposal from this Reconciliation.")
        elif node_type == "proposal":
            self.action_help.update("Action Help: Run Learning from this Proposal, or compare with another Proposal.")
        elif node_type == "review":
            self.action_help.update("Action Help: Compare with another Review, or inspect weaknesses and personas.")
        elif node_type == "learning":
            self.action_help.update("Action Help: Inspect insights and reusable patterns, or compare with another Learning record.")
        else:
            self.action_help.update("Action Help: Navigate the pipeline from Project to Learning.")

    def format_compare_label(self, node_type, data):
        if node_type == "project":
            return data.get("name", data.get("project_id", "Project"))
        if node_type == "version":
            return ensure_alias("version", data.get("version_id", ""))
        if node_type == "review":
            return ensure_alias("review", data.get("review_id", ""))
        if node_type == "reconciliation":
            return ensure_alias("reconciliation", data.get("recon_id", ""))
        if node_type == "proposal":
            return ensure_alias("proposal", data.get("proposal_id", ""))
        if node_type == "learning":
            return ensure_alias("learning", data.get("learning_id", ""))
        return node_type

    def render_details(self, node_type, data):
        if node_type == "project":
            text = f"""PROJECT
-------
Name: {data.get("name", "")}
Project ID: {data.get("project_id", "")}
Created: {data.get("created_at", "")}
"""
        elif node_type == "version":
            summary = data.get("version_summary", {})
            text = f"""VERSION
-------
Name: {ensure_alias("version", data.get("version_id", ""))}
Version ID: {data.get("version_id", "")}

Client Ask:
{summary.get("client_ask", "")}

Architecture:
{summary.get("architecture_understanding", "")}

Missing Information:
{chr(10).join("- " + x for x in summary.get("missing_information", [])) if summary.get("missing_information") else "None"}
"""
        elif node_type == "review":
            result = data.get("result", {})
            summary = result.get("summary", {})
            weaknesses = result.get("weaknesses", [])
            personas = data.get("personas") or result.get("personas", [])

            weakness_lines = "\n".join(
                f"- {friendly_category(w.get('category'))}: {first_sentence(w.get('description', ''))}"
                for w in weaknesses[:5]
            ) or "None"

            text = f"""REVIEW
------
Name: {ensure_alias("review", data.get("review_id", ""))}
Review ID: {data.get("review_id", "")}
Version ID: {data.get("version_id", "")}
Status: {data.get("status", "")}
Personas: {", ".join(personas) if personas else "None"}

Overall Assessment:
{summary.get("overall_assessment", "")}

Top Weaknesses:
{weakness_lines}
"""
        elif node_type == "reconciliation":
            merged = data.get("merged_weaknesses", [])
            summary = data.get("summary", {})
            risk_lines = "\n".join(
                f"- {friendly_category(w.get('category'))}: severity={w.get('severity', '')}, count={w.get('count', 0)}"
                for w in merged[:5]
            ) or "None"

            text = f"""RECONCILIATION
--------------
Name: {ensure_alias("reconciliation", data.get("recon_id", ""))}
Recon ID: {data.get("recon_id", "")}
Source Reviews: {", ".join(data.get("source_reviews", []))}
Merged Weaknesses:
{risk_lines}

Consensus Findings:
{", ".join(summary.get("consensus_findings", [])) if summary.get("consensus_findings") else "None"}

Recommended Focus:
{chr(10).join("- " + x for x in summary.get("recommended_focus", [])[:5]) if summary.get("recommended_focus") else "None"}
"""
        elif node_type == "proposal":
            summary = data.get("summary", {})
            recs = data.get("recommendations", [])

            rec_lines = "\n".join(
                f"- {friendly_category(r.get('category'))}: {first_sentence(r.get('recommendation', ''))}"
                for r in recs[:5]
            ) or "None"

            text = f"""PROPOSAL
--------
Name: {ensure_alias("proposal", data.get("proposal_id", ""))}
Proposal ID: {data.get("proposal_id", "")}
Source Type: {data.get("source_type", "")}
Source ID: {data.get("source_id", "")}

Executive Summary:
{summary.get("executive_summary", "")}

Recommended Solution:
{summary.get("recommended_solution", "")}

Top Recommendations:
{rec_lines}
"""
        elif node_type == "learning":
            insights = data.get("insights", [])
            patterns = data.get("reusable_patterns", [])
            suggestions = data.get("suggested_prompt_updates", [])

            insight_lines = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:3]) or "None"
            pattern_lines = "\n".join(f"- {p.get('pattern', '')}" for p in patterns[:3]) or "None"
            suggestion_lines = "\n".join(f"- {first_sentence(s.get('suggestion', ''))}" for s in suggestions[:3]) or "None"

            text = f"""LEARNING
--------
Name: {ensure_alias("learning", data.get("learning_id", ""))}
Learning ID: {data.get("learning_id", "")}
Source Type: {data.get("source_type", "")}
Source ID: {data.get("source_id", "")}
Approved: {data.get("approved", False)}

Insights:
{insight_lines}

Reusable Patterns:
{pattern_lines}

Prompt Suggestions:
{suggestion_lines}
"""
        else:
            text = json.dumps(data, indent=2)

        self.details_output.update(text)

    def render_learning_panel(self, node_type, data):
        if node_type == "learning":
            insights = data.get("insights", [])
            text = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:5]) or "No insights"
            self.learning_output.update(text)
            return

        if node_type == "proposal":
            learning_items = api_get("/learning")
            related = [l for l in learning_items if l.get("source_type") == "proposal" and l.get("source_id") == data.get("proposal_id")]
            if related:
                latest = related[-1]
                insights = latest.get("insights", [])
                text = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:5]) or "No related insights"
                self.learning_output.update(text)
            else:
                self.learning_output.update("No learning record linked to this proposal yet.")
            return

        self.learning_output.update("Select a Learning node, or a Proposal that has Learning output.")

    # -----------------------------------------------------
    # Actions
    # -----------------------------------------------------

    def on_button_pressed(self, event):
        node = self.pipeline_tree.cursor_node
        if not node or not node.data:
            self.ui_log("Select a node first")
            return

        node_type, data = node.data
        personas = [p.strip() for p in self.input_personas.value.split(",") if p.strip()]
        context = self.input_context.value.strip()

        if event.button.id == "btn_review":
            if node_type != "version":
                self.ui_log("Run Review requires a Version selected")
                return

            result = api_post("/reviews", {"version_id": data["version_id"]})
            if result:
                self.ui_log(f"✅ Review created: {ensure_alias('review', result.get('review_id', ''))}")
            else:
                self.ui_log("❌ Failed to create review")

            self.load_tree()
            return

        if event.button.id == "btn_iteration":
            if node_type == "review":
                version_id = data.get("version_id")
            elif node_type == "version":
                version_id = data.get("version_id")
            else:
                self.ui_log("Run Iteration requires a Version or Review selected")
                return

            result = api_post("/reviews", {
                "version_id": version_id,
                "personas": personas,
                "user_context": context
            })
            if result:
                self.ui_log(f"✅ Iteration-style review created: {ensure_alias('review', result.get('review_id', ''))}")
            else:
                self.ui_log("❌ Failed to create iteration review")

            self.load_tree()
            return

        if event.button.id == "btn_reconcile":
            if node_type == "version":
                version_id = data.get("version_id")
            elif node_type == "review":
                version_id = data.get("version_id")
            else:
                self.ui_log("Run Reconcile requires a Version or Review selected")
                return

            reviews = api_get("/reviews")
            version_reviews = [r for r in reviews if r.get("version_id") == version_id]

            if len(version_reviews) < 2:
                self.ui_log("⚠️ Need at least 2 reviews on the selected version")
                return

            review_ids = [r["review_id"] for r in version_reviews[-2:]]
            result = api_post("/reconciliation", {"review_ids": review_ids})

            if result:
                self.ui_log(f"✅ Reconciliation created: {ensure_alias('reconciliation', result.get('recon_id', ''))}")
            else:
                self.ui_log("❌ Failed to create reconciliation")

            self.load_tree()
            return

        if event.button.id == "btn_proposal":
            if node_type != "reconciliation":
                self.ui_log("Run Proposal requires a Reconciliation selected")
                return

            result = api_post("/proposal", {"recon_id": data["recon_id"]})
            if result:
                self.ui_log(f"✅ Proposal created: {ensure_alias('proposal', result.get('proposal_id', ''))}")
            else:
                self.ui_log("❌ Failed to create proposal")

            self.load_tree()
            return

        if event.button.id == "btn_learning":
            if node_type != "proposal":
                self.ui_log("Run Learning requires a Proposal selected")
                return

            result = api_post("/learning", {
                "source_type": "proposal",
                "source_id": data["proposal_id"]
            })
            if result:
                self.ui_log(f"✅ Learning created: {ensure_alias('learning', result.get('learning_id', ''))}")
            else:
                self.ui_log("❌ Failed to create learning")

            self.load_tree()
            return

        if event.button.id == "btn_compare":
            self.compare_mode = True
            self.compare_nodes = []
            self.compare_output.update("Compare mode ON\nSelect A and B nodes of the same type")
            self.ui_log("Compare mode ON")
            return

        if event.button.id == "btn_refresh":
            self.load_tree()
            self.ui_log("Refreshed")
            return

    # -----------------------------------------------------
    # Compare
    # -----------------------------------------------------

    def render_compare(self):
        if len(self.compare_nodes) != 2:
            return

        (type_a, data_a), (type_b, data_b) = self.compare_nodes

        if type_a != type_b:
            self.compare_output.update("❌ Cannot compare different node types")
            return

        if type_a == "review":
            a_summary = data_a.get("result", {}).get("summary", {}).get("overall_assessment", "")
            b_summary = data_b.get("result", {}).get("summary", {}).get("overall_assessment", "")

            a_weaknesses = data_a.get("result", {}).get("weaknesses", [])
            b_weaknesses = data_b.get("result", {}).get("weaknesses", [])

            a_lines = "\n".join(
                f"- {friendly_category(w.get('category'))}: {first_sentence(w.get('description', ''))}"
                for w in a_weaknesses[:3]
            ) or "None"
            b_lines = "\n".join(
                f"- {friendly_category(w.get('category'))}: {first_sentence(w.get('description', ''))}"
                for w in b_weaknesses[:3]
            ) or "None"

            text = f"""A = {ensure_alias('review', data_a.get('review_id', ''))}
{a_summary}

Top:
{a_lines}

------------------------------

B = {ensure_alias('review', data_b.get('review_id', ''))}
{b_summary}

Top:
{b_lines}
"""
            self.compare_output.update(text)
            return

        if type_a == "proposal":
            a_summary = data_a.get("summary", {}).get("executive_summary", "")
            b_summary = data_b.get("summary", {}).get("executive_summary", "")

            text = f"""A = {ensure_alias('proposal', data_a.get('proposal_id', ''))}
{a_summary}

------------------------------

B = {ensure_alias('proposal', data_b.get('proposal_id', ''))}
{b_summary}
"""
            self.compare_output.update(text)
            return

        if type_a == "learning":
            a_insights = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in data_a.get("insights", [])[:3]) or "None"
            b_insights = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in data_b.get("insights", [])[:3]) or "None"

            text = f"""A = {ensure_alias('learning', data_a.get('learning_id', ''))}
{a_insights}

------------------------------

B = {ensure_alias('learning', data_b.get('learning_id', ''))}
{b_insights}
"""
            self.compare_output.update(text)
            return

        self.compare_output.update("Compare is implemented for Review, Proposal, and Learning only.")


if __name__ == "__main__":
    ContextaOperatorConsole().run()
