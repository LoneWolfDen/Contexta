from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static, Input, Button, Label
from textual.containers import Horizontal, Vertical
from pathlib import Path
from datetime import datetime
import requests
import json
import re
import traceback
from typing import Any, Dict, List

BASE_URL = "http://localhost:5000"

ALIASES_DIR = Path("tools/contexta_runs")
ALIASES_FILE = ALIASES_DIR / "aliases.json"
DEBUG_LOG_FILE = ALIASES_DIR / "v6_2_debug.log"
ALIASES_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Debug helpers
# =========================================================

def debug_log(*parts):
    try:
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(" ".join(str(p) for p in parts) + "\n")
    except Exception:
        pass


# =========================================================
# Safe JSON / payload helpers
# =========================================================

def parse_json_maybe(value: Any) -> Any:
    """Parse JSON repeatedly for double/triple encoded JSON strings."""
    while isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        if text.startswith("{") or text.startswith("["):
            try:
                value = json.loads(text)
                continue
            except Exception:
                return value
        return value
    return value


def normalize_payload(value: Any) -> Any:
    """Recursively normalize nested JSON strings inside dicts/lists."""
    value = parse_json_maybe(value)

    if isinstance(value, dict):
        return {k: normalize_payload(v) for k, v in value.items()}

    if isinstance(value, list):
        return [normalize_payload(v) for v in value]

    return value


def to_dict(value: Any) -> Dict[str, Any]:
    value = normalize_payload(value)
    return value if isinstance(value, dict) else {}


def to_list(value: Any) -> List[Any]:
    value = normalize_payload(value)
    return value if isinstance(value, list) else []


def ensure_entity_shape(obj: Any, entity_type: str = "") -> Dict[str, Any]:
    """Make API objects safe for UI access."""
    data = normalize_payload(obj)
    if not isinstance(data, dict):
        return {}

    if entity_type == "version":
        data["version_summary"] = to_dict(data.get("version_summary"))

    elif entity_type == "review":
        data["result"] = to_dict(data.get("result"))
        data["personas"] = to_list(data.get("personas"))
        result = data["result"]
        result["summary"] = to_dict(result.get("summary"))
        result["weaknesses"] = to_list(result.get("weaknesses"))
        result["personas"] = to_list(result.get("personas"))

    elif entity_type == "reconciliation":
        data["merged_weaknesses"] = to_list(data.get("merged_weaknesses"))
        data["summary"] = to_dict(data.get("summary"))
        data["review_ids"] = to_list(data.get("review_ids"))
        data["source_reviews"] = to_list(data.get("source_reviews"))

    elif entity_type == "proposal":
        data["summary"] = to_dict(data.get("summary"))
        data["recommendations"] = to_list(data.get("recommendations"))

    elif entity_type == "learning":
        data["insights"] = to_list(data.get("insights"))
        data["reusable_patterns"] = to_list(data.get("reusable_patterns"))
        data["suggested_prompt_updates"] = to_list(data.get("suggested_prompt_updates"))

    return data


def normalize_entity_list(items: Any, entity_type: str) -> List[Dict[str, Any]]:
    items = normalize_payload(items)
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        norm = normalize_payload(item)
        if isinstance(norm, dict):
            out.append(ensure_entity_shape(norm, entity_type))
    return out


# =========================================================
# API helpers
# =========================================================

def api_get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}")
        if not r.ok:
            debug_log("GET failed", path, "status", r.status_code)
            return []
        payload = normalize_payload(r.json())
        debug_log("GET", path, "type", type(payload).__name__)
        return payload
    except Exception as e:
        debug_log("GET exception", path, repr(e))
        return []


def api_post(path, payload):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=payload)
        if not r.ok:
            debug_log("POST failed", path, "status", r.status_code, "payload", payload)
            return None
        result = normalize_payload(r.json())
        debug_log("POST", path, "type", type(result).__name__)
        return result
    except Exception as e:
        debug_log("POST exception", path, repr(e), "payload", payload)
        return None


# =========================================================
# Alias helpers
# =========================================================

def load_aliases():
    if not ALIASES_FILE.exists():
        return {}
    try:
        with open(ALIASES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_aliases(data):
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ts():
    return datetime.now().strftime("%d%m%Y_%H%M%S")


def slug(text: str, fallback: str = "Item"):
    if not text:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(text).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or fallback


def derive_persona_tag(personas):
    personas = to_list(personas)
    if not personas:
        return "Base"

    short_map = {
        "Architect": "Arch",
        "Delivery Lead": "Del",
        "Security": "Sec",
    }

    parts = []
    for p in personas:
        parts.append(short_map.get(str(p), slug(str(p), "Ctx")[:6]))

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
        aliases[key] = {"display": display_label, "full": full_alias}
        save_aliases(aliases)
    return aliases[key]


def get_alias(obj_type: str, obj_id: str):
    aliases = load_aliases()
    return aliases.get(alias_key(obj_type, obj_id))


def get_alias_display(obj_type: str, obj_id: str, fallback: str = ""):
    alias = get_alias(obj_type, obj_id)
    return alias["display"] if alias else fallback


def ensure_project_alias(project):
    project = ensure_entity_shape(project, "project")
    obj_id = project.get("project_id", "")
    project_name = project.get("name", "Project")
    existing = get_alias("project", obj_id)
    if existing:
        return existing
    full_alias = f"Project_{slug(project_name, 'Project')}_{ts()}"
    display = f"📁 {project_name}"
    return register_alias("project", obj_id, display, full_alias)


def ensure_version_alias(version, project):
    version = ensure_entity_shape(version, "version")
    project = ensure_entity_shape(project, "project")
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
    review = ensure_entity_shape(review, "review")
    obj_id = review.get("review_id", "")
    existing = get_alias("review", obj_id)
    if existing:
        return existing
    aliases = load_aliases()
    persons = review.get("personas") or review.get("result", {}).get("personas", [])
    tag = derive_persona_tag(persons)
    version_tag = str(version_alias_display).replace("📦 ", "") or "V?"
    idx = count_existing(aliases, f"Review_{version_tag}_")
    full_alias = f"Review_{version_tag}_{tag}_{ts()}_{idx:02d}"
    display = f"📝 R[{tag}]-{idx:02d}"
    return register_alias("review", obj_id, display, full_alias)


def ensure_recon_alias(recon, version_alias_display, version_review_aliases):
    recon = ensure_entity_shape(recon, "reconciliation")
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
    version_tag = str(version_alias_display).replace("📦 ", "") or "V?"
    idx = count_existing(aliases, f"Reconciliation_{version_tag}_")
    full_alias = f"Reconciliation_{version_tag}_{review_part}_{ts()}_{idx:02d}"
    display = f"🔗 Recon[{version_tag}_{review_part}]-{idx:02d}"
    return register_alias("reconciliation", obj_id, display, full_alias)


def ensure_proposal_alias(proposal, recon_alias_display):
    proposal = ensure_entity_shape(proposal, "proposal")
    obj_id = proposal.get("proposal_id", "")
    existing = get_alias("proposal", obj_id)
    if existing:
        return existing
    aliases = load_aliases()
    recon_tag = str(recon_alias_display).replace("🔗 ", "") or "Recon"
    idx = count_existing(aliases, "Proposal_")
    full_alias = f"Proposal_{slug(recon_tag, 'Recon')}_{ts()}_{idx:02d}"
    display = f"📄 Prop[{recon_tag}]-{idx:02d}"
    return register_alias("proposal", obj_id, display, full_alias)


def ensure_learning_alias(learning, proposal_alias_display):
    learning = ensure_entity_shape(learning, "learning")
    obj_id = learning.get("learning_id", "")
    existing = get_alias("learning", obj_id)
    if existing:
        return existing
    aliases = load_aliases()
    prop_tag = str(proposal_alias_display).replace("📄 ", "") or "Proposal"
    idx = count_existing(aliases, "Learning_")
    full_alias = f"Learning_{slug(prop_tag, 'Proposal')}_{ts()}_{idx:02d}"
    display = f"📘 Learn[{prop_tag}]-{idx:02d}"
    return register_alias("learning", obj_id, display, full_alias)


# =========================================================
# Friendly display helpers
# =========================================================

def friendly_category(cat):
    cat = str(cat or "")
    if not cat:
        return "Other"
    if "missing_information" in cat:
        return "Missing key inputs"
    if "missing_security_context" in cat:
        return "Security gaps"
    return cat.replace("_", " ").title()


def first_sentence(text):
    text = str(text or "").strip()
    if not text:
        return ""
    first = text.split(".")[0].strip()
    return first + ("." if first and not first.endswith(".") else "")


def bullet_lines(values, field=None, limit=None, formatter=None):
    values = to_list(values)
    if limit is not None:
        values = values[:limit]
    if not values:
        return "None"
    lines = []
    for item in values:
        try:
            if formatter:
                rendered = formatter(item)
            elif field and isinstance(item, dict):
                rendered = item.get(field, "")
            else:
                rendered = str(item)
            rendered = str(rendered).strip()
            if rendered:
                lines.append(f"- {rendered}")
        except Exception as e:
            debug_log("bullet_lines item error", repr(e), "item_type", type(item).__name__, "item", str(item)[:300])
    return "\n".join(lines) if lines else "None"


# =========================================================
# Main App
# =========================================================

class ContextaOperatorConsole(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #left_panel { width: 32%; border-right: solid #555; }
    #right_panel { width: 68%; padding: 0 1; }
    #top_right { height: 1fr; }
    #details_panel { width: 52%; border-right: solid #444; padding: 1; }
    #analysis_panel { width: 48%; padding: 1; }
    #compare_panel { height: 50%; border-bottom: solid #444; }
    #learning_panel { height: 50%; padding-top: 1; }
    #details_output, #compare_output, #learning_output { overflow-y: auto; }
    #run_panel { height: 12; border-top: solid #666; padding: 1; }
    #action_row { height: auto; margin-top: 1; margin-bottom: 1; }
    Button { margin-right: 1; }
    Input { margin-bottom: 1; }
    .section_title { text-style: bold; }
    #log_panel { height: 3; border-top: solid #444; padding-top: 1; }
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
        DEBUG_LOG_FILE.write_text("", encoding="utf-8")
        self.load_tree()

    def ui_log(self, text):
        self.log_output.update(str(text))
        debug_log("UI", text)

    def load_tree(self):
        root = self.pipeline_tree.root
        root.remove_children()
        root.label = "Contexta Pipeline"
        root.expand()

        projects = normalize_entity_list(api_get("/projects"), "project")
        versions = normalize_entity_list(api_get("/versions"), "version")
        reviews = normalize_entity_list(api_get("/reviews"), "review")
        recons = normalize_entity_list(api_get("/reconciliation"), "reconciliation")
        proposals = normalize_entity_list(api_get("/proposal"), "proposal")
        learning_items = normalize_entity_list(api_get("/learning"), "learning")

        for project in projects:
            p_alias = ensure_project_alias(project)
            p_id = project.get("project_id", "")
            p_node = root.add(p_alias["display"], data=("project", project))
            p_versions = [v for v in versions if v.get("project_id") == p_id]

            for version in p_versions:
                v_alias = ensure_version_alias(version, project)
                v_id = version.get("version_id", "")
                v_node = p_node.add(v_alias["display"], data=("version", version))

                version_reviews = [r for r in reviews if r.get("version_id") == v_id]
                review_ids = [r.get("review_id") for r in version_reviews if r.get("review_id")]
                reviews_group = v_node.add("📝 Reviews", None)
                for review in version_reviews:
                    r_alias = ensure_review_alias(review, v_alias["display"])
                    reviews_group.add(r_alias["display"], data=("review", review))

                matched_recons = []
                recon_group = v_node.add("🔗 Reconciliation", None)
                for recon in recons:
                    ids = to_list(recon.get("review_ids") or recon.get("source_reviews"))
                    if any(rid in ids for rid in review_ids):
                        matched_recons.append(recon)
                        rec_alias = ensure_recon_alias(recon, v_alias["display"], review_ids)
                        recon_group.add(rec_alias["display"], data=("reconciliation", recon))

                matched_props = []
                proposal_group = v_node.add("📄 Proposals", None)
                recon_ids = [r.get("recon_id") for r in matched_recons if r.get("recon_id")]
                for proposal in proposals:
                    if proposal.get("source_type") == "reconciliation" and proposal.get("source_id") in recon_ids:
                        related_recon = next((x for x in matched_recons if x.get("recon_id") == proposal.get("source_id")), None)
                        recon_alias = ensure_recon_alias(related_recon, v_alias["display"], review_ids) if related_recon else {"display": "Recon"}
                        prop_alias = ensure_proposal_alias(proposal, recon_alias["display"])
                        proposal_group.add(prop_alias["display"], data=("proposal", proposal))
                        matched_props.append((proposal, prop_alias))

                learning_group = v_node.add("📘 Learning", None)
                for proposal, proposal_alias in matched_props:
                    for learning in learning_items:
                        if learning.get("source_type") == "proposal" and learning.get("source_id") == proposal.get("proposal_id"):
                            l_alias = ensure_learning_alias(learning, proposal_alias["display"])
                            learning_group.add(l_alias["display"], data=("learning", learning))
        self.pipeline_tree.focus()

    def on_tree_node_selected(self, event):
        node = event.node
        if not node.data:
            return
        try:
            node_type, data = node.data
            data = ensure_entity_shape(normalize_payload(data), node_type)
            debug_log("SELECT", node_type, "data_type", type(data).__name__, "keys", list(data.keys()) if isinstance(data, dict) else "NA")
            if node_type == "review":
                debug_log("REVIEW TYPES",
                          "result", type(data.get("result")).__name__,
                          "summary", type(to_dict(data.get("result")).get("summary")).__name__,
                          "weaknesses", type(to_dict(data.get("result")).get("weaknesses")).__name__)
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
        except Exception as e:
            debug_log("on_tree_node_selected ERROR", repr(e))
            debug_log(traceback.format_exc())
            self.details_output.update(f"Error while rendering node. Check debug log: {DEBUG_LOG_FILE}")
            self.ui_log(f"❌ Render error: {type(e).__name__}")

    def format_scope_label(self, node_type, data):
        data = ensure_entity_shape(normalize_payload(data), node_type)
        if node_type == "project":
            alias = get_alias("project", data.get("project_id", ""))
            return alias["display"] if alias else data.get("name", data.get("project_id", "Project"))
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

    def render_details(self, node_type, data):
        data = ensure_entity_shape(normalize_payload(data), node_type)
        debug_log("RENDER DETAILS", node_type)

        if node_type == "project":
            text = f"""PROJECT
-------
Display: {self.format_scope_label(node_type, data)}
Name: {data.get('name', '')}
Project ID: {data.get('project_id', '')}
Created: {data.get('created_at', '')}
"""

        elif node_type == "version":
            alias = get_alias("version", data.get("version_id", "")) or {}
            summary = to_dict(data.get("version_summary"))
            # support alternative field names safely
            client_ask = summary.get("client_ask") or summary.get("solution_understanding") or ""
            architecture = summary.get("architecture_understanding") or summary.get("technology_landscape") or ""
            missing_info = bullet_lines(summary.get("missing_information"))
            text = f"""VERSION
-------
Display: {alias.get('display', '')}
Full: {alias.get('full', '')}
Version ID: {data.get('version_id', '')}

Client Ask:
{client_ask}

Architecture:
{architecture}

Missing Information:
{missing_info}
"""

        elif node_type == "review":
            alias = get_alias("review", data.get("review_id", "")) or {}
            result = to_dict(data.get("result"))
            summary = to_dict(result.get("summary"))
            weaknesses = to_list(result.get("weaknesses"))
            personas = to_list(data.get("personas") or result.get("personas"))
            key_findings = to_list(summary.get("key_findings"))
            recommended_focus = to_list(summary.get("recommended_focus"))

            weakness_lines = bullet_lines(
                weaknesses,
                limit=5,
                formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: {first_sentence(to_dict(w).get('description', ''))}"
            )
            findings_lines = bullet_lines(key_findings, limit=3)
            focus_lines = bullet_lines(recommended_focus, limit=3)

            text = f"""REVIEW
------
Display: {alias.get('display', '')}
Full: {alias.get('full', '')}
Review ID: {data.get('review_id', '')}
Version ID: {data.get('version_id', '')}
Status: {data.get('status', '')}
Personas: {', '.join(str(p) for p in personas) if personas else 'None'}

Overall Assessment:
{summary.get('overall_assessment', '')}

Key Findings:
{findings_lines}

Top Weaknesses:
{weakness_lines}

Recommended Focus:
{focus_lines}
"""

        elif node_type == "reconciliation":
            alias = get_alias("reconciliation", data.get("recon_id", "")) or {}
            merged = to_list(data.get("merged_weaknesses"))
            summary = to_dict(data.get("summary"))
            source_reviews = to_list(data.get("source_reviews") or data.get("review_ids"))
            risk_lines = bullet_lines(
                merged,
                limit=5,
                formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: severity={to_dict(w).get('severity', '')}, count={to_dict(w).get('count', 0)}"
            )
            consensus = bullet_lines(summary.get("consensus_findings"))
            text = f"""RECONCILIATION
--------------
Display: {alias.get('display', '')}
Full: {alias.get('full', '')}
Recon ID: {data.get('recon_id', '')}
Source Reviews: {', '.join(source_reviews) if source_reviews else 'None'}

Merged Weaknesses:
{risk_lines}

Consensus Findings:
{consensus}
"""

        elif node_type == "proposal":
            alias = get_alias("proposal", data.get("proposal_id", "")) or {}
            summary = to_dict(data.get("summary"))
            recs = to_list(data.get("recommendations"))
            rec_lines = bullet_lines(
                recs,
                limit=5,
                formatter=lambda r: f"{friendly_category(to_dict(r).get('category'))}: {first_sentence(to_dict(r).get('recommendation', ''))}"
            )
            text = f"""PROPOSAL
--------
Display: {alias.get('display', '')}
Full: {alias.get('full', '')}
Proposal ID: {data.get('proposal_id', '')}
Source Type: {data.get('source_type', '')}
Source ID: {data.get('source_id', '')}

Executive Summary:
{summary.get('executive_summary', '')}

Recommended Solution:
{summary.get('recommended_solution', '')}

Top Recommendations:
{rec_lines}
"""

        elif node_type == "learning":
            alias = get_alias("learning", data.get("learning_id", "")) or {}
            insights = to_list(data.get("insights"))
            patterns = to_list(data.get("reusable_patterns"))
            suggestions = to_list(data.get("suggested_prompt_updates"))
            insight_lines = bullet_lines(insights, limit=3, formatter=lambda i: first_sentence(to_dict(i).get('detail', '')))
            pattern_lines = bullet_lines(patterns, limit=3, formatter=lambda p: to_dict(p).get('pattern', ''))
            suggestion_lines = bullet_lines(suggestions, limit=3, formatter=lambda s: first_sentence(to_dict(s).get('suggestion', '')))
            text = f"""LEARNING
--------
Display: {alias.get('display', '')}
Full: {alias.get('full', '')}
Learning ID: {data.get('learning_id', '')}
Source Type: {data.get('source_type', '')}
Source ID: {data.get('source_id', '')}
Approved: {data.get('approved', False)}

Insights:
{insight_lines}

Reusable Patterns:
{pattern_lines}

Prompt Suggestions:
{suggestion_lines}
"""

        else:
            text = json.dumps(normalize_payload(data), indent=2, ensure_ascii=False)

        self.details_output.update(text)

    def render_learning_panel(self, node_type, data):
        data = ensure_entity_shape(normalize_payload(data), node_type)
        if node_type == "learning":
            insights = to_list(data.get("insights"))
            patterns = to_list(data.get("reusable_patterns"))
            text = "Insights:\n" + bullet_lines(insights, limit=5, formatter=lambda i: first_sentence(to_dict(i).get('detail', '')))
            text += "\n\nPatterns:\n" + bullet_lines(patterns, limit=5, formatter=lambda p: to_dict(p).get('pattern', ''))
            self.learning_output.update(text)
            return

        if node_type == "proposal":
            learning_items = normalize_entity_list(api_get("/learning"), "learning")
            related = [l for l in learning_items if l.get("source_type") == "proposal" and l.get("source_id") == data.get("proposal_id")]
            if related:
                latest = related[-1]
                insights = to_list(latest.get("insights"))
                text = "Related Learning:\n" + bullet_lines(insights, limit=5, formatter=lambda i: first_sentence(to_dict(i).get('detail', '')))
                self.learning_output.update(text)
            else:
                self.learning_output.update("No learning linked to this proposal yet.")
            return

        self.learning_output.update("Select a Learning node, or a Proposal that has Learning output.")

    def on_button_pressed(self, event):
        node = self.pipeline_tree.cursor_node
        if not node or not node.data:
            self.ui_log("Select a node first")
            return

        node_type, data = node.data
        data = ensure_entity_shape(normalize_payload(data), node_type)
        personas = [p.strip() for p in self.input_personas.value.split(",") if p.strip()]
        context = self.input_context.value.strip()

        if event.button.id == "btn_review":
            if node_type != "version":
                self.ui_log("Run Review requires a Version selected")
                return
            result = ensure_entity_shape(api_post("/reviews", {"version_id": data.get("version_id")}), "review")
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
            version_id = data.get("version_id")
            version_display = get_alias_display("version", version_id, version_id)
            result = ensure_entity_shape(api_post("/reviews", {
                "version_id": version_id,
                "personas": personas,
                "user_context": context,
            }), "review")
            if result:
                ensure_review_alias(result, version_display)
                self.ui_log(f"✅ Iteration-style review created: {self.format_scope_label('review', result)}")
            else:
                self.ui_log("❌ Failed to create iteration review")
            self.load_tree()
            return

        if event.button.id == "btn_reconcile":
            if node_type not in {"version", "review"}:
                self.ui_log("Run Reconcile requires a Version or Review selected")
                return
            version_id = data.get("version_id")
            version_display = get_alias_display("version", version_id, version_id)
            reviews = normalize_entity_list(api_get("/reviews"), "review")
            version_reviews = [r for r in reviews if r.get("version_id") == version_id]
            if len(version_reviews) < 2:
                self.ui_log("⚠️ Need at least 2 reviews on the selected version")
                return
            review_ids = [r["review_id"] for r in version_reviews[-2:] if r.get("review_id")]
            result = ensure_entity_shape(api_post("/reconciliation", {"review_ids": review_ids}), "reconciliation")
            if result:
                ensure_recon_alias(result, version_display, review_ids)
                self.ui_log(f"✅ Reconciliation created: {self.format_scope_label('reconciliation', result)}")
            else:
                self.ui_log("❌ Failed to create reconciliation")
            self.load_tree()
            return

        if event.button.id == "btn_proposal":
            if node_type != "reconciliation":
                self.ui_log("Run Proposal requires a Reconciliation selected")
                return
            result = ensure_entity_shape(api_post("/proposal", {"recon_id": data.get("recon_id")}), "proposal")
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
            result = ensure_entity_shape(api_post("/learning", {
                "source_type": "proposal",
                "source_id": data.get("proposal_id"),
            }), "learning")
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

    def render_compare(self):
        if len(self.compare_nodes) != 2:
            return
        (type_a, data_a), (type_b, data_b) = self.compare_nodes
        data_a = ensure_entity_shape(normalize_payload(data_a), type_a)
        data_b = ensure_entity_shape(normalize_payload(data_b), type_b)

        if type_a != type_b:
            self.compare_output.update("❌ Cannot compare different node types")
            return

        if type_a == "review":
            a_label = self.format_scope_label("review", data_a)
            b_label = self.format_scope_label("review", data_b)
            a_result = to_dict(data_a.get("result"))
            b_result = to_dict(data_b.get("result"))
            a_summary = to_dict(a_result.get("summary")).get("overall_assessment", "")
            b_summary = to_dict(b_result.get("summary")).get("overall_assessment", "")
            a_weaknesses = to_list(a_result.get("weaknesses"))
            b_weaknesses = to_list(b_result.get("weaknesses"))
            a_lines = bullet_lines(a_weaknesses, limit=3, formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: {first_sentence(to_dict(w).get('description', ''))}")
            b_lines = bullet_lines(b_weaknesses, limit=3, formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: {first_sentence(to_dict(w).get('description', ''))}")
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
            a_summary = to_dict(data_a.get("summary")).get("executive_summary", "")
            b_summary = to_dict(data_b.get("summary")).get("executive_summary", "")
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
            a_insights = bullet_lines(to_list(data_a.get("insights"))[:3], formatter=lambda i: first_sentence(to_dict(i).get('detail', '')))
            b_insights = bullet_lines(to_list(data_b.get("insights"))[:3], formatter=lambda i: first_sentence(to_dict(i).get('detail', '')))
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
