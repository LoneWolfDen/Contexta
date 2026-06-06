from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Tree, Static, Input, Button, Label
)
from textual.containers import Horizontal, Vertical
from pathlib import Path
from datetime import datetime
import requests
import json
import re

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
# Alias helpers
# =========================================================

def load_aliases():
    if not ALIASES_FILE.exists():
        return {}
    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_aliases(data):
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ts():
    return datetime.now().strftime("%d%m%Y_%H%M%S")


def slug(text: str, fallback: str = "Item"):
    if not text:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or fallback


def derive_persona_tag(personas):
    if not personas:
        return "Base"

    short_map = {
        "Architect": "Arch",
        "Delivery Lead": "Del",
        "Security": "Sec",
    }

    parts = []
    for p in personas:
        parts.append(short_map.get(p, slug(p, "Ctx")[:6]))

    return "+".join(parts)


def alias_key(obj_type: str, obj_id: str):
    return f"{obj_type}:{obj_id}"


def count_existing(aliases, prefix):
    count = 0
    for val in aliases.values():
        if isinstance(val, dict) and val.get("full", "").startswith(prefix):
            count += 1
    return count + 1


def register_alias(obj_type: str, obj_id: str, display_label: str, full_alias: str):
    aliases = load_aliases()
    key = alias_key(obj_type, obj_id)
    if key not in aliases:
        aliases[key] = {
            "display": display_label,
            "full": full_alias
        }
        save_aliases(aliases)
    return aliases[key]


def get_alias(obj_type: str, obj_id: str):
    aliases = load_aliases()
    return aliases.get(alias_key(obj_type, obj_id))


def ensure_project_alias(project):
    obj_id = project.get("project_id", "")
    project_name = project.get("name", "Project")
    existing = get_alias("project", obj_id)
    if existing:
        return existing

    full_alias = f"Project_{slug(project_name, 'Project')}_{ts()}"
    display = f"📁 {project_name}"
    return register_alias("project", obj_id, display, full_alias)


def ensure_version_alias(version, project):
    obj_id = version.get("version_id", "")
    existing = get_alias("version", obj_id)
    if existing:
        return existing

    aliases = load_aliases()
    project_name = slug(project.get("name", "Project"), "Project")
    idx = count_existing(aliases, f"Version_{project_name}_")
    full_alias = f"Version_{project_name}_{ts()}_{idx:02d}"
    display = f"📦 V{idx}"
    return register_alias("version", obj_id, display, full_alias)


def ensure_review_alias(review, version_alias_display):
    obj_id = review.get("review_id", "")
    existing = get_alias("review", obj_id)
    if existing:
        return existing

    aliases = load_aliases()
    persons = review.get("personas") or review.get("result", {}).get("personas", [])
    tag = derive_persona_tag(persons)

    version_tag = version_alias_display.replace("📦 ", "")
    idx = count_existing(aliases, f"Review_{version_tag}_")
    full_alias = f"Review_{version_tag}_{tag}_{ts()}_{idx:02d}"
    display = f"📝 R[{tag}]-{idx:02d}"
    return register_alias("review", obj_id, display, full_alias)


def ensure_recon_alias(recon, version_alias_display, version_review_aliases):
    obj_id = recon.get("recon_id", "")
    existing = get_alias("reconciliation", obj_id)
    if existing:
        return existing

    aliases = load_aliases()
    review_ids = recon.get("review_ids") or recon.get("source_reviews") or []

    short_review_tokens = []
    for rid in review_ids[:2]:
        a = get_alias("review", rid)
        if a:
            short_review_tokens.append(a["display"].replace("📝 ", "").replace("R[", "R").replace("]", ""))
    review_part = "_".join(short_review_tokens) if short_review_tokens else "R1_R2"

    version_tag = version_alias_display.replace("📦 ", "")
    idx = count_existing(aliases, f"Reconciliation_{version_tag}_")
    full_alias = f"Reconciliation_{version_tag}_{review_part}_{ts()}_{idx:02d}"
    display = f"🔗 Recon[{version_tag}_{review_part}]-{idx:02d}"
    return register_alias("reconciliation", obj_id, display, full_alias)


def ensure_proposal_alias(proposal, recon_alias_display):
    obj_id = proposal.get("proposal_id", "")
    existing = get_alias("proposal", obj_id)
    if existing:
        return existing

    aliases = load_aliases()
    recon_tag = recon_alias_display.replace("🔗 ", "")
    idx = count_existing(aliases, "Proposal_")
    full_alias = f"Proposal_{slug(recon_tag, 'Recon')}_{ts()}_{idx:02d}"
    display = f"📄 Prop[{recon_tag}]-{idx:02d}"
    return register_alias("proposal", obj_id, display, full_alias)


def ensure_learning_alias(learning, proposal_alias_display):
    obj_id = learning.get("learning_id", "")
    existing = get_alias("learning", obj_id)
    if existing:
        return existing

    aliases = load_aliases()
    prop_tag = proposal_alias_display.replace("📄 ", "")
    idx = count_existing(aliases, "Learning_")
    full_alias = f"Learning_{slug(prop_tag, 'Proposal')}_{ts()}_{idx:02d}"
    display = f"📘 Learn[{prop_tag}]-{idx:02d}"
    return register_alias("learning", obj_id, display, full_alias)


# =========================================================
# Friendly display helpers
# =========================================================

def friendly_category(cat):
    if not cat:
        return "Other"
    if "missing_information" in cat:
        return "Missing key inputs"
    if "missing_security_context" in cat:
        return "Security gaps"
    return cat.replace("_", " ").title()


def first_sentence(text):
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
        width: 52%;
        border-right: solid #444;
        padding: 1;
    }

    #analysis_panel {
        width: 48%;
        padding: 1;
    }

    #compare_panel {
        height: 50%;
        border-bottom: solid #444;
    }

    #learning_panel {
        height: 50%;
        padding-top: 1;
    }

    #details_output, #compare_output, #learning_output {
        overflow-y: auto;
    }

    #run_panel {
        height: 12;
        border-top: solid #666;
        padding: 1;
    }

    #action_row {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
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

            with Vertical(id="left_panel"):
                yield Static("Pipeline Explorer", classes="section_title")
                yield Tree("Contexta Pipeline", id="pipeline_tree")

            with Vertical(id="right_panel"):

                with Horizontal(id="top_right"):

                    with Vertical(id="details_panel"):
                        yield Static("Details", classes="section_title")
                        yield Static("Select a node from the tree", id="details_output")

                    with Vertical(id="analysis_panel"):

                        with Vertical(id="compare_panel"):
                            yield Static("Compare", classes="section_title")
                            yield Static("Press Compare Mode, then select A and B nodes", id="compare_output")

                        with Vertical(id="learning_panel"):
                            yield Static("Learning", classes="section_title")
                            yield Static("Select a Learning node, or a Proposal linked to Learning", id="learning_output")

                with Vertical(id="run_panel"):
                    yield Static("Run Controls", classes="section_title")
                    yield Label("Selected Scope: None", id="selected_scope")
                    yield Label("Action: Select an action below. Inputs are used only where needed.", id="action_help")

                    yield Input(placeholder="Personas (used for Iteration / Persona Review, e.g. Architect,Security)", id="input_personas")
                    yield Input(placeholder="User context (used for Iteration / Persona Review)", id="input_context")

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

    def ui_log(self, text):
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
            p_alias = ensure_project_alias(project)
            p_id = project.get("project_id", "")

            p_node = root.add(
                p_alias["display"],
                data=("project", project)
            )

            p_versions = [v for v in versions if v.get("project_id") == p_id]

            for version in p_versions:
                v_alias = ensure_version_alias(version, project)
                v_id = version.get("version_id", "")

                v_node = p_node.add(
                    v_alias["display"],
                    data=("version", version)
                )

                version_reviews = [r for r in reviews if r.get("version_id") == v_id]
                review_ids = [r.get("review_id") for r in version_reviews]

                reviews_group = v_node.add("📝 Reviews", None)

                for review in version_reviews:
                    r_alias = ensure_review_alias(review, v_alias["display"])
                    reviews_group.add(
                        r_alias["display"],
                        data=("review", review)
                    )

                recon_group = v_node.add("🔗 Reconciliation", None)
                matched_recons = []

                for recon in recons:
                    ids = recon.get("review_ids") or recon.get("source_reviews") or []
                    if any(rid in ids for rid in review_ids):
                        matched_recons.append(recon)
                        rec_alias = ensure_recon_alias(recon, v_alias["display"], review_ids)
                        recon_group.add(
                            rec_alias["display"],
                            data=("reconciliation", recon)
                        )

                proposal_group = v_node.add("📄 Proposals", None)
                matched_props = []

                recon_ids = [r.get("recon_id") for r in matched_recons]

                for proposal in proposals:
                    if proposal.get("source_type") == "reconciliation" and proposal.get("source_id") in recon_ids:
                        # find related recon alias
                        related_recon = next((x for x in matched_recons if x.get("recon_id") == proposal.get("source_id")), None)
                        recon_alias = ensure_recon_alias(related_recon, v_alias["display"], review_ids) if related_recon else {"display": "Recon"}
                        p_alias = ensure_proposal_alias(proposal, recon_alias["display"])
                        proposal_group.add(
                            p_alias["display"],
                            data=("proposal", proposal)
                        )
                        matched_props.append((proposal, p_alias))

                learning_group = v_node.add("📘 Learning", None)

                for proposal, proposal_alias in matched_props:
                    for learning in learning_items:
                        if learning.get("source_type") == "proposal" and learning.get("source_id") == proposal.get("proposal_id"):
                            l_alias = ensure_learning_alias(learning, proposal_alias["display"])
                            learning_group.add(
                                l_alias["display"],
                                data=("learning", learning)
                            )

        self.pipeline_tree.focus()

    # -----------------------------------------------------
    # Selection
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
                self.compare_output.update(f"A selected: {self.format_scope_label(node_type, data)}\nSelect second item...")
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
    # Scope labels
    # -----------------------------------------------------

    def format_scope_label(self, node_type, data):
        if node_type == "project":
            return data.get("name", data.get("project_id", "Project"))
        if node_type == "version":
            a = get_alias("version", data.get("version_id", ""))
            return a["display"] if a else data.get("version_id", "")
        if node_type == "review":
            a = get_alias("review", data.get("review_id", ""))
            return a["display"] if a else data.get("review_id", "")
        if node_type == "reconciliation":
            a = get_alias("reconciliation", data.get("recon_id", ""))
            return a["display"] if a else data.get("recon_id", "")
        if node_type == "proposal":
            a = get_alias("proposal", data.get("proposal_id", ""))
            return a["display"] if a else data.get("proposal_id", "")
        if node_type == "learning":
            a = get_alias("learning", data.get("learning_id", ""))
            return a["display"] if a else data.get("learning_id", "")
        return node_type

    def update_selected_scope(self, node_type, data):
        self.selected_scope.update(f"Selected Scope: {self.format_scope_label(node_type, data)}")

        if node_type == "version":
            self.action_help.update("Action: Use Run Review for baseline or Run Iteration with Personas + Context.")
        elif node_type == "review":
            self.action_help.update("Action: Use Compare Mode with another Review, or Run Reconcile if enough reviews exist.")
        elif node_type == "reconciliation":
            self.action_help.update("Action: Use Run Proposal.")
        elif node_type == "proposal":
            self.action_help.update("Action: Use Run Learning, or Compare Mode with another Proposal.")
        elif node_type == "learning":
            self.action_help.update("Action: Use Compare Mode with another Learning record.")
        else:
            self.action_help.update("Action: Navigate the pipeline. Run actions are enabled on Version / Review / Reconciliation / Proposal.")

    # -----------------------------------------------------
    # Detail / learning rendering
    # -----------------------------------------------------

    def render_details(self, node_type, data):
        if node_type == "project":
            text = f"""PROJECT
-------
Display: {self.format_scope_label(node_type, data)}
Name: {data.get("name", "")}
Project ID: {data.get("project_id", "")}
Created: {data.get("created_at", "")}
"""
        elif node_type == "version":
            alias = get_alias("version", data.get("version_id", "")) or {}
            summary = data.get("version_summary", {})
            text = f"""VERSION
-------
Display: {alias.get("display", "")}
Full: {alias.get("full", "")}
Version ID: {data.get("version_id", "")}

Client Ask:
{summary.get("client_ask", "")}

Architecture:
{summary.get("architecture_understanding", "")}

Missing Information:
{chr(10).join("- " + x for x in summary.get("missing_information", [])) if summary.get("missing_information") else "None"}
"""
        elif node_type == "review":
            alias = get_alias("review", data.get("review_id", "")) or {}
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
Display: {alias.get("display", "")}
Full: {alias.get("full", "")}
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
            alias = get_alias("reconciliation", data.get("recon_id", "")) or {}
            merged = data.get("merged_weaknesses", [])
            summary = data.get("summary", {})

            risk_lines = "\n".join(
                f"- {friendly_category(w.get('category'))}: severity={w.get('severity', '')}, count={w.get('count', 0)}"
                for w in merged[:5]
            ) or "None"

            text = f"""RECONCILIATION
--------------
Display: {alias.get("display", "")}
Full: {alias.get("full", "")}
Recon ID: {data.get("recon_id", "")}
Source Reviews: {", ".join(data.get("source_reviews", []))}

Merged Weaknesses:
{risk_lines}

Consensus Findings:
{", ".join(summary.get("consensus_findings", [])) if summary.get("consensus_findings") else "None"}
"""
        elif node_type == "proposal":
            alias = get_alias("proposal", data.get("proposal_id", "")) or {}
            summary = data.get("summary", {})
            recs = data.get("recommendations", [])

            rec_lines = "\n".join(
                f"- {friendly_category(r.get('category'))}: {first_sentence(r.get('recommendation', ''))}"
                for r in recs[:5]
            ) or "None"

            text = f"""PROPOSAL
--------
Display: {alias.get("display", "")}
Full: {alias.get("full", "")}
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
            alias = get_alias("learning", data.get("learning_id", "")) or {}
            insights = data.get("insights", [])
            patterns = data.get("reusable_patterns", [])
            suggestions = data.get("suggested_prompt_updates", [])

            insight_lines = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:3]) or "None"
            pattern_lines = "\n".join(f"- {p.get('pattern', '')}" for p in patterns[:3]) or "None"
            suggestion_lines = "\n".join(f"- {first_sentence(s.get('suggestion', ''))}" for s in suggestions[:3]) or "None"

            text = f"""LEARNING
--------
Display: {alias.get("display", "")}
Full: {alias.get("full", "")}
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
            patterns = data.get("reusable_patterns", [])
            text = "Insights:\n" + ("\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:5]) or "None")
            text += "\n\nPatterns:\n" + ("\n".join(f"- {p.get('pattern', '')}" for p in patterns[:5]) or "None")
            self.learning_output.update(text)
            return

        if node_type == "proposal":
            learning_items = api_get("/learning")
            related = [l for l in learning_items if l.get("source_type") == "proposal" and l.get("source_id") == data.get("proposal_id")]
            if related:
                latest = related[-1]
                insights = latest.get("insights", [])
                text = "Related Learning:\n" + ("\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in insights[:5]) or "None")
                self.learning_output.update(text)
            else:
                self.learning_output.update("No learning linked to this proposal yet.")
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
                ensure_review_alias(result, self.format_scope_label("version", data))
                self.ui_log(f"✅ Review created: {self.format_scope_label('review', result)}")
            else:
                self.ui_log("❌ Failed to create review")

            self.load_tree()
            return

        if event.button.id == "btn_iteration":
            if node_type not in {"version", "review"}:
                self.ui_log("Run Iteration requires a Version or Review selected")
                return

            version_id = data.get("version_id") if node_type == "review" else data.get("version_id")

            result = api_post("/reviews", {
                "version_id": version_id,
                "personas": personas,
                "user_context": context
            })
            if result:
                ensure_review_alias(result, self.format_scope_label("version", {"version_id": version_id}))
                self.ui_log(f"✅ Iteration-style review created: {self.format_scope_label('review', result)}")
            else:
                self.ui_log("❌ Failed to create iteration review")

            self.load_tree()
            return

        if event.button.id == "btn_reconcile":
            if node_type not in {"version", "review"}:
                self.ui_log("Run Reconcile requires a Version or Review selected")
                return

            version_id = data.get("version_id") if node_type == "review" else data.get("version_id")
            reviews = api_get("/reviews")
            version_reviews = [r for r in reviews if r.get("version_id") == version_id]

            if len(version_reviews) < 2:
                self.ui_log("⚠️ Need at least 2 reviews on the selected version")
                return

            review_ids = [r["review_id"] for r in version_reviews[-2:]]
            result = api_post("/reconciliation", {"review_ids": review_ids})

            if result:
                ensure_recon_alias(result, self.format_scope_label("version", {"version_id": version_id}), review_ids)
                self.ui_log(f"✅ Reconciliation created: {self.format_scope_label('reconciliation', result)}")
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
                ensure_proposal_alias(result, self.format_scope_label("reconciliation", data))
                self.ui_log(f"✅ Proposal created: {self.format_scope_label('proposal', result)}")
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
                ensure_learning_alias(result, self.format_scope_label("proposal", data))
                self.ui_log(f"✅ Learning created: {self.format_scope_label('learning', result)}")
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
    # Compare rendering
    # -----------------------------------------------------

    def render_compare(self):
        if len(self.compare_nodes) != 2:
            return

        (type_a, data_a), (type_b, data_b) = self.compare_nodes

        if type_a != type_b:
            self.compare_output.update("❌ Cannot compare different node types")
            return

        if type_a == "review":
            a_label = self.format_scope_label("review", data_a)
            b_label = self.format_scope_label("review", data_b)

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

            self.compare_output.update(f"""A = {a_label}
{a_summary}

Top:
{a_lines}

------------------------------

B = {b_label}
{b_summary}

Top:
{b_lines}
""")
            return

        if type_a == "proposal":
            a_label = self.format_scope_label("proposal", data_a)
            b_label = self.format_scope_label("proposal", data_b)

            a_summary = data_a.get("summary", {}).get("executive_summary", "")
            b_summary = data_b.get("summary", {}).get("executive_summary", "")

            self.compare_output.update(f"""A = {a_label}
{a_summary}

------------------------------

B = {b_label}
{b_summary}
""")
            return

        if type_a == "learning":
            a_label = self.format_scope_label("learning", data_a)
            b_label = self.format_scope_label("learning", data_b)

            a_insights = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in data_a.get("insights", [])[:3]) or "None"
            b_insights = "\n".join(f"- {first_sentence(i.get('detail', ''))}" for i in data_b.get("insights", [])[:3]) or "None"

            self.compare_output.update(f"""A = {a_label}
{a_insights}

------------------------------

B = {b_label}
{b_insights}
""")
            return

        self.compare_output.update("Compare is implemented for Review, Proposal, and Learning only.")


if __name__ == "__main__":
    ContextaOperatorConsole().run()
