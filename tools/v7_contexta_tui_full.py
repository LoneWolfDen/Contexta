# v7_2_contexta_tui_full.py
# Contexta TUI v7.2
# Grouped pipeline view (Option B), version-aware naming, top menu, contextual second line,
# compare mode, risk panel, and run actions for review / iteration / reconciliation / proposal / learning.

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

import requests
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Tree, Static, Input, Button, Label

BASE_URL = "http://localhost:5000"


# =========================================================
# Safe JSON helpers
# =========================================================

def parse_json_maybe(value: Any) -> Any:
    # Handles dict/list already parsed, and double/triple encoded JSON strings.
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


def ensure_entity(entity: Any, entity_type: str = "") -> Dict[str, Any]:
    data = to_dict(entity)
    if not data:
        return {}

    if entity_type == "version":
        data["version_summary"] = to_dict(data.get("version_summary"))
        data["artifact_snapshot"] = to_list(data.get("artifact_snapshot"))
    elif entity_type == "review":
        data["result"] = to_dict(data.get("result"))
        data["personas"] = to_list(data.get("personas"))
        result = data["result"]
        result["summary"] = to_dict(result.get("summary"))
        result["weaknesses"] = to_list(result.get("weaknesses"))
        result["personas"] = to_list(result.get("personas"))
    elif entity_type == "reconciliation":
        data["review_ids"] = to_list(data.get("review_ids"))
        data["source_reviews"] = to_list(data.get("source_reviews"))
        data["summary"] = to_dict(data.get("summary"))
        data["merged_weaknesses"] = to_list(data.get("merged_weaknesses"))
    elif entity_type == "proposal":
        data["summary"] = to_dict(data.get("summary"))
        data["recommendations"] = to_list(data.get("recommendations"))
        data["references"] = to_list(data.get("references"))
    elif entity_type == "learning":
        data["insights"] = to_list(data.get("insights"))
        data["reusable_patterns"] = to_list(data.get("reusable_patterns"))
        data["suggested_prompt_updates"] = to_list(data.get("suggested_prompt_updates"))
    return data


def normalize_entity_list(items: Any, entity_type: str) -> List[Dict[str, Any]]:
    items = to_list(items)
    out: List[Dict[str, Any]] = []
    for item in items:
        entry = ensure_entity(item, entity_type)
        if entry:
            out.append(entry)
    return out


# =========================================================
# API helpers
# =========================================================

def api_get(path: str):
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=30)
        if not r.ok:
            return []
        return normalize_payload(r.json())
    except Exception:
        return []


def api_post(path: str, payload: Dict[str, Any]):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=payload, timeout=60)
        if not r.ok:
            return None
        return normalize_payload(r.json())
    except Exception:
        return None


# =========================================================
# Display helpers
# =========================================================

def first_sentence(text: Any) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    first = text.split(".")[0].strip()
    if not first:
        return ""
    return first if first.endswith(".") else first + "."


def friendly_category(cat: Any) -> str:
    cat = str(cat or "")
    if not cat:
        return "Other"
    if cat == "missing_information":
        return "Missing key inputs"
    if cat == "missing_security_context":
        return "Security gaps"
    return cat.replace("_", " ").title()


def bullet_lines(values: Any, limit: Optional[int] = None, formatter=None) -> str:
    items = to_list(values)
    if limit is not None:
        items = items[:limit]
    if not items:
        return "None"
    lines = []
    for item in items:
        rendered = formatter(item) if formatter else str(item)
        rendered = str(rendered or "").strip()
        if rendered:
            lines.append(f"- {rendered}")
    return "\n".join(lines) if lines else "None"


def safe_dt(text: Any) -> str:
    s = str(text or "")
    return s[:19].replace("T", " ") if s else ""


# =========================================================
# Data model and naming
# =========================================================

def dedupe_by_id(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        value = item.get(key)
        if value and value not in seen:
            seen.add(value)
            out.append(item)
    return out


def persona_tag(review: Dict[str, Any]) -> str:
    personas = to_list(review.get("personas") or to_dict(review.get("result")).get("personas"))
    if not personas:
        return "Base"
    short_map = {
        "architect": "Arch",
        "security": "Sec",
        "delivery lead": "Del",
        "delivery": "Del",
        "operations": "Ops",
        "platform": "Plat",
        "network": "Net",
        "compliance": "Comp",
    }
    parts = []
    for p in personas:
        label = str(p).strip()
        if not label:
            continue
        parts.append(short_map.get(label.lower(), label[:4].capitalize()))
    return "+".join(parts) if parts else "Base"


def build_model() -> Dict[str, Any]:
    projects = dedupe_by_id(normalize_entity_list(api_get("/projects"), "project"), "project_id")
    versions = dedupe_by_id(normalize_entity_list(api_get("/versions"), "version"), "version_id")
    reviews = dedupe_by_id(normalize_entity_list(api_get("/reviews"), "review"), "review_id")
    recons = dedupe_by_id(normalize_entity_list(api_get("/reconciliation"), "reconciliation"), "recon_id")
    proposals = dedupe_by_id(normalize_entity_list(api_get("/proposal"), "proposal"), "proposal_id")
    learning = dedupe_by_id(normalize_entity_list(api_get("/learning"), "learning"), "learning_id")

    versions_by_project: Dict[str, List[Dict[str, Any]]] = {}
    for version in versions:
        versions_by_project.setdefault(version.get("project_id"), []).append(version)

    # Sort for deterministic sequence numbering.
    for plist in versions_by_project.values():
        plist.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("version_id", ""))))

    version_labels: Dict[str, str] = {}
    project_version_seq: Dict[str, Dict[str, int]] = {}
    for project in projects:
        pid = project.get("project_id")
        seq_map: Dict[str, int] = {}
        for i, version in enumerate(versions_by_project.get(pid, []), start=1):
            vid = version.get("version_id")
            seq_map[vid] = i
            version_labels[vid] = f"V{i}"
        project_version_seq[pid] = seq_map

    reviews_by_version: Dict[str, List[Dict[str, Any]]] = {}
    for review in reviews:
        reviews_by_version.setdefault(review.get("version_id"), []).append(review)
    for rlist in reviews_by_version.values():
        rlist.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("review_id", ""))))

    review_display: Dict[str, str] = {}
    review_seq: Dict[str, int] = {}
    review_to_version: Dict[str, str] = {}
    for vid, rlist in reviews_by_version.items():
        vlabel = version_labels.get(vid, "V?")
        for i, review in enumerate(rlist, start=1):
            rid = review.get("review_id")
            review_seq[rid] = i
            review_to_version[rid] = vid
            review_display[rid] = f"R[{vlabel}_{persona_tag(review)}_{i:02d}]"

    recons_by_version: Dict[str, List[Dict[str, Any]]] = {}
    recon_display: Dict[str, str] = {}
    recon_seq: Dict[str, int] = {}
    recon_to_version: Dict[str, str] = {}
    for recon in recons:
        review_ids = to_list(recon.get("review_ids") or recon.get("source_reviews"))
        if not review_ids:
            continue
        vid = review_to_version.get(review_ids[0])
        if not vid:
            # Fallback by scanning reviews
            first_rid = review_ids[0]
            match_review = next((r for r in reviews if r.get("review_id") == first_rid), None)
            vid = match_review.get("version_id") if match_review else None
        if not vid:
            continue
        recons_by_version.setdefault(vid, []).append(recon)
        recon_to_version[recon.get("recon_id")] = vid

    for vid, rclist in recons_by_version.items():
        rclist.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("recon_id", ""))))
        vlabel = version_labels.get(vid, "V?")
        for i, recon in enumerate(rclist, start=1):
            rcid = recon.get("recon_id")
            recon_seq[rcid] = i
            tokens = []
            for rid in to_list(recon.get("review_ids") or recon.get("source_reviews")):
                idx = review_seq.get(rid)
                if idx:
                    tokens.append(f"R{idx:02d}")
            token_text = "_".join(tokens) if tokens else "R??"
            recon_display[rcid] = f"Recon[{vlabel}_{token_text}]"

    proposals_by_version: Dict[str, List[Dict[str, Any]]] = {}
    proposal_display: Dict[str, str] = {}
    proposal_seq: Dict[str, int] = {}
    proposal_to_version: Dict[str, str] = {}
    for proposal in proposals:
        rcid = proposal.get("source_id")
        vid = recon_to_version.get(rcid)
        if vid:
            proposals_by_version.setdefault(vid, []).append(proposal)
            proposal_to_version[proposal.get("proposal_id")] = vid

    for vid, plist in proposals_by_version.items():
        plist.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("proposal_id", ""))))
        vlabel = version_labels.get(vid, "V?")
        for i, proposal in enumerate(plist, start=1):
            pid = proposal.get("proposal_id")
            proposal_seq[pid] = i
            rcid = proposal.get("source_id")
            rec_no = recon_seq.get(rcid, i)
            proposal_display[pid] = f"Prop[{vlabel}_Rec{rec_no:02d}]"

    learning_by_version: Dict[str, List[Dict[str, Any]]] = {}
    learning_display: Dict[str, str] = {}
    for items in []:
        pass
    for item in learning:
        pid = item.get("source_id")
        vid = proposal_to_version.get(pid)
        if vid:
            learning_by_version.setdefault(vid, []).append(item)

    for vid, llist in learning_by_version.items():
        llist.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("learning_id", ""))))
        vlabel = version_labels.get(vid, "V?")
        for i, item in enumerate(llist, start=1):
            lid = item.get("learning_id")
            pid = item.get("source_id")
            prop_no = proposal_seq.get(pid, i)
            learning_display[lid] = f"Learn[{vlabel}_Prop{prop_no:02d}]"

    return {
        "projects": projects,
        "versions": versions,
        "reviews": reviews,
        "recons": recons,
        "proposals": proposals,
        "learning": learning,
        "versions_by_project": versions_by_project,
        "reviews_by_version": reviews_by_version,
        "recons_by_version": recons_by_version,
        "proposals_by_version": proposals_by_version,
        "learning_by_version": learning_by_version,
        "version_labels": version_labels,
        "review_display": review_display,
        "recon_display": recon_display,
        "proposal_display": proposal_display,
        "learning_display": learning_display,
        "review_seq": review_seq,
        "recon_seq": recon_seq,
        "proposal_seq": proposal_seq,
    }


# =========================================================
# App
# =========================================================

class ContextaV72(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #menu_bar {
        height: 3;
        border-bottom: solid #444;
        padding: 0 1;
    }

    #context_bar {
        height: 3;
        border-bottom: solid #333;
        padding: 0 1;
    }

    #body {
        height: 1fr;
    }

    #left_panel {
        width: 34%;
        border-right: solid #555;
        padding: 0 1;
    }

    #right_panel {
        width: 66%;
        padding: 0 1;
    }

    #details_panel {
        height: 54%;
        border-bottom: solid #444;
        padding: 1;
    }

    #analysis_panel {
        height: 30%;
        border-bottom: solid #444;
        padding: 1;
    }

    #controls_panel {
        height: 16%;
        padding: 1;
    }

    #compare_output, #risk_output, #details_output {
        overflow-y: auto;
    }

    #control_row, #menu_row {
        height: auto;
    }

    Button {
        margin-right: 1;
        min-width: 12;
    }

    Input {
        margin-top: 1;
        margin-bottom: 1;
    }

    .title {
        text-style: bold;
    }

    #log_output {
        border-top: solid #333;
        padding-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Top single-line menu
        with Vertical(id="menu_bar"):
            with Horizontal(id="menu_row"):
                yield Button("Project", id="mode_project")
                yield Button("Version", id="mode_version")
                yield Button("Review", id="mode_review")
                yield Button("Recon", id="mode_recon")
                yield Button("Proposal", id="mode_proposal")
                yield Button("Learning", id="mode_learning")
                yield Button("Compare", id="mode_compare")
                yield Button("Refresh", id="mode_refresh")

        # Contextual second line
        with Vertical(id="context_bar"):
            yield Label("Mode: Review", id="mode_label")
            yield Label("Context: Select a node from the tree. Compare mode accepts two items of the same type.", id="context_label")

        with Horizontal(id="body"):
            with Vertical(id="left_panel"):
                yield Static("Pipeline Explorer", classes="title")
                yield Tree("Contexta Pipeline", id="pipeline_tree")

            with Vertical(id="right_panel"):
                with Vertical(id="details_panel"):
                    yield Static("Details", classes="title")
                    yield Static("Select a node from the tree", id="details_output")

                with Vertical(id="analysis_panel"):
                    yield Static("Compare and Risk", classes="title")
                    yield Static("Compare panel is ready. Choose Compare from the top menu, then select two nodes of the same type.", id="compare_output")
                    yield Static("Risk summary will appear here when a Review, Reconciliation, Proposal, or Learning node is selected.", id="risk_output")

                with Vertical(id="controls_panel"):
                    yield Static("Run Controls", classes="title")
                    with Horizontal(id="control_row"):
                        yield Button("Run Review", id="btn_review")
                        yield Button("Run Iteration", id="btn_iteration")
                        yield Button("Run Reconcile", id="btn_reconcile")
                        yield Button("Run Proposal", id="btn_proposal")
                        yield Button("Run Learning", id="btn_learning")
                    yield Input(placeholder="Personas, for example Architect,Security", id="input_personas")
                    yield Input(placeholder="User context for iteration or persona review", id="input_context")
                    yield Static("Ready", id="log_output")

        yield Footer()

    # -----------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------

    def on_mount(self):
        self.pipeline_tree = self.query_one("#pipeline_tree", Tree)
        self.details_output = self.query_one("#details_output", Static)
        self.compare_output = self.query_one("#compare_output", Static)
        self.risk_output = self.query_one("#risk_output", Static)
        self.mode_label = self.query_one("#mode_label", Label)
        self.context_label = self.query_one("#context_label", Label)
        self.input_personas = self.query_one("#input_personas", Input)
        self.input_context = self.query_one("#input_context", Input)
        self.log_output = self.query_one("#log_output", Static)

        self.ui_mode = "Review"
        self.compare_mode = False
        self.compare_type: Optional[str] = None
        self.compare_nodes: List[Tuple[str, Dict[str, Any], str]] = []
        self.model = {}
        self.reload_all()

    # -----------------------------------------------------
    # Data / tree
    # -----------------------------------------------------

    def reload_all(self):
        self.model = build_model()
        self.load_tree()
        self.ui_log("Refreshed pipeline data")

    def load_tree(self):
        root = self.pipeline_tree.root
        root.remove_children()
        root.label = "Contexta Pipeline"
        root.expand()

        for project in self.model.get("projects", []):
            pid = project.get("project_id")
            pnode = root.add(f"📁 {project.get('name', 'Project')}", data=("project", project, project.get("name", "Project")))

            versions = self.model.get("versions_by_project", {}).get(pid, [])
            for version in versions:
                vid = version.get("version_id")
                vlabel = self.model.get("version_labels", {}).get(vid, "V?")
                vnode = pnode.add(f"📦 {vlabel}", data=("version", version, vlabel))

                reviews_group = vnode.add("📝 Reviews")
                for review in self.model.get("reviews_by_version", {}).get(vid, []):
                    rid = review.get("review_id")
                    display = self.model.get("review_display", {}).get(rid, rid)
                    reviews_group.add(display, data=("review", review, display))

                recon_group = vnode.add("🔗 Reconciliation")
                for recon in self.model.get("recons_by_version", {}).get(vid, []):
                    rcid = recon.get("recon_id")
                    display = self.model.get("recon_display", {}).get(rcid, rcid)
                    recon_group.add(display, data=("reconciliation", recon, display))

                proposal_group = vnode.add("📄 Proposals")
                for proposal in self.model.get("proposals_by_version", {}).get(vid, []):
                    pid2 = proposal.get("proposal_id")
                    display = self.model.get("proposal_display", {}).get(pid2, pid2)
                    proposal_group.add(display, data=("proposal", proposal, display))

                learning_group = vnode.add("📘 Learning")
                for item in self.model.get("learning_by_version", {}).get(vid, []):
                    lid = item.get("learning_id")
                    display = self.model.get("learning_display", {}).get(lid, lid)
                    learning_group.add(display, data=("learning", item, display))

        self.pipeline_tree.focus()

    # -----------------------------------------------------
    # Logging / labels
    # -----------------------------------------------------

    def ui_log(self, text: str):
        self.log_output.update(text)

    def set_mode(self, mode_name: str):
        self.ui_mode = mode_name
        self.mode_label.update(f"Mode: {mode_name}")
        if mode_name == "Compare":
            self.compare_mode = True
            self.compare_type = None
            self.compare_nodes = []
            self.context_label.update("Compare context: Select item 1 from the tree, then item 2 of the same type. Supported: Review, Proposal, Learning.")
            self.compare_output.update("Compare mode is ON\nSelected option 1: —\nSelected option 2: —")
            self.ui_log("Compare mode ON")
        else:
            self.compare_mode = False
            self.compare_type = None
            self.compare_nodes = []
            self.context_label.update(f"Context: {mode_name}. Select a node from the tree to work with this mode.")

    # -----------------------------------------------------
    # Top menu
    # -----------------------------------------------------

    def on_button_pressed(self, event):
        button_id = event.button.id or ""

        # Top mode menu
        if button_id.startswith("mode_"):
            if button_id == "mode_refresh":
                self.reload_all()
                return
            mode_lookup = {
                "mode_project": "Project",
                "mode_version": "Version",
                "mode_review": "Review",
                "mode_recon": "Recon",
                "mode_proposal": "Proposal",
                "mode_learning": "Learning",
                "mode_compare": "Compare",
            }
            self.set_mode(mode_lookup.get(button_id, "Review"))
            return

        # Run actions
        node = self.pipeline_tree.cursor_node
        if not node or not node.data:
            self.ui_log("Select a node first")
            return

        node_type, data, display = node.data
        personas = [p.strip() for p in self.input_personas.value.split(",") if p.strip()]
        context = self.input_context.value.strip()

        if button_id == "btn_review":
            if node_type != "version":
                self.ui_log("Run Review requires a Version selected")
                return
            result = api_post("/reviews", {"version_id": data.get("version_id")})
            if result:
                self.reload_all()
                self.ui_log("Review created")
            else:
                self.ui_log("Failed to create review")
            return

        if button_id == "btn_iteration":
            if node_type not in {"version", "review"}:
                self.ui_log("Run Iteration requires a Version or Review selected")
                return
            version_id = data.get("version_id")
            result = api_post("/reviews", {
                "version_id": version_id,
                "personas": personas,
                "user_context": context,
            })
            if result:
                self.reload_all()
                self.ui_log("Iteration review created")
            else:
                self.ui_log("Failed to create iteration review")
            return

        if button_id == "btn_reconcile":
            if node_type not in {"version", "review"}:
                self.ui_log("Run Reconcile requires a Version or Review selected")
                return
            version_id = data.get("version_id")
            version_reviews = self.model.get("reviews_by_version", {}).get(version_id, [])
            review_ids = [r.get("review_id") for r in version_reviews if r.get("review_id")]
            if len(review_ids) < 2:
                self.ui_log("Need at least 2 reviews on the selected version")
                return
            result = api_post("/reconciliation", {"review_ids": review_ids})
            if result:
                self.reload_all()
                self.ui_log("Reconciliation created")
            else:
                self.ui_log("Failed to create reconciliation")
            return

        if button_id == "btn_proposal":
            if node_type != "reconciliation":
                self.ui_log("Run Proposal requires a Reconciliation selected")
                return
            result = api_post("/proposal", {"recon_id": data.get("recon_id")})
            if result:
                self.reload_all()
                self.ui_log("Proposal created")
            else:
                self.ui_log("Failed to create proposal")
            return

        if button_id == "btn_learning":
            if node_type != "proposal":
                self.ui_log("Run Learning requires a Proposal selected")
                return
            result = api_post("/learning", {
                "source_type": "proposal",
                "source_id": data.get("proposal_id"),
            })
            if result:
                self.reload_all()
                self.ui_log("Learning created")
            else:
                self.ui_log("Failed to create learning")
            return

    # -----------------------------------------------------
    # Selection
    # -----------------------------------------------------

    def on_tree_node_selected(self, event):
        node = event.node
        if not node.data:
            return

        node_type, data, display = node.data
        self.context_label.update(f"Context: {self.ui_mode} | Selected: {display}")
        self.render_details(node_type, data, display)
        self.render_risk(node_type, data)

        if self.compare_mode and node_type in {"review", "proposal", "learning"}:
            if self.compare_type is None:
                self.compare_type = node_type
            if node_type != self.compare_type:
                self.compare_output.update(f"Compare mode only supports the same type. Current expected type: {self.compare_type.title()}")
                return
            self.compare_nodes.append((node_type, data, display))
            if len(self.compare_nodes) == 1:
                _, _, d1 = self.compare_nodes[0]
                self.compare_output.update(f"Compare mode is ON\nSelected option 1: {d1}\nSelected option 2: —")
                return
            if len(self.compare_nodes) == 2:
                self.render_compare()
                self.compare_mode = False
                self.compare_type = None
                self.compare_nodes = []
                self.mode_label.update("Mode: Compare")
                self.context_label.update("Compare complete. Select Compare again to start a new comparison.")
                self.ui_log("Compare complete")
                return

    # -----------------------------------------------------
    # Renderers
    # -----------------------------------------------------

    def render_details(self, node_type: str, data: Dict[str, Any], display: str):
        if node_type == "project":
            text = f"""PROJECT
-------
Display: {display}
Name: {data.get('name', '')}
Project ID: {data.get('project_id', '')}
Created: {safe_dt(data.get('created_at'))}
"""
            self.details_output.update(text)
            return

        if node_type == "version":
            summary = to_dict(data.get("version_summary"))
            missing_info = bullet_lines(summary.get("missing_information"), limit=5)
            artifact_count = len(to_list(data.get("artifact_snapshot")))
            text = f"""VERSION
-------
Display: {display}
Version ID: {data.get('version_id', '')}
Artifacts in snapshot: {artifact_count}
Created: {safe_dt(data.get('created_at'))}

Client Ask:
{summary.get('client_ask', '')}

Architecture Understanding:
{summary.get('architecture_understanding', '')}

Missing Information:
{missing_info}
"""
            self.details_output.update(text)
            return

        if node_type == "review":
            result = to_dict(data.get("result"))
            summary = to_dict(result.get("summary"))
            weaknesses = to_list(result.get("weaknesses"))
            personas = to_list(data.get("personas") or result.get("personas"))
            findings = bullet_lines(summary.get("key_findings"), limit=4)
            focus = bullet_lines(summary.get("recommended_focus"), limit=4)
            weakness_lines = bullet_lines(
                weaknesses,
                limit=5,
                formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: {first_sentence(to_dict(w).get('description'))}",
            )
            text = f"""REVIEW
------
Display: {display}
Review ID: {data.get('review_id', '')}
Version ID: {data.get('version_id', '')}
Status: {data.get('status', '')}
Created: {safe_dt(data.get('created_at'))}
Personas: {', '.join(str(x) for x in personas) if personas else 'None'}

Overall Assessment:
{summary.get('overall_assessment', '')}

Key Findings:
{findings}

Top Weaknesses:
{weakness_lines}

Recommended Focus:
{focus}
"""
            self.details_output.update(text)
            return

        if node_type == "reconciliation":
            summary = to_dict(data.get("summary"))
            merged = to_list(data.get("merged_weaknesses"))
            merged_lines = bullet_lines(
                merged,
                limit=6,
                formatter=lambda w: f"{friendly_category(to_dict(w).get('category'))}: severity={to_dict(w).get('severity', '')}, count={to_dict(w).get('count', 0)}",
            )
            text = f"""RECONCILIATION
--------------
Display: {display}
Recon ID: {data.get('recon_id', '')}
Created: {safe_dt(data.get('created_at'))}
Source Reviews: {', '.join(to_list(data.get('source_reviews') or data.get('review_ids'))) or 'None'}

Merged Weaknesses:
{merged_lines}

Consensus Findings:
{bullet_lines(summary.get('consensus_findings'), limit=6)}
"""
            self.details_output.update(text)
            return

        if node_type == "proposal":
            summary = to_dict(data.get("summary"))
            recs = bullet_lines(
                data.get("recommendations"),
                limit=6,
                formatter=lambda r: f"{friendly_category(to_dict(r).get('category'))}: {first_sentence(to_dict(r).get('recommendation'))}",
            )
            text = f"""PROPOSAL
--------
Display: {display}
Proposal ID: {data.get('proposal_id', '')}
Source Type: {data.get('source_type', '')}
Source ID: {data.get('source_id', '')}
Created: {safe_dt(data.get('created_at'))}

Executive Summary:
{summary.get('executive_summary', '')}

Problem Statement:
{summary.get('problem_statement', '')}

Recommended Solution:
{summary.get('recommended_solution', '')}

Top Recommendations:
{recs}
"""
            self.details_output.update(text)
            return

        if node_type == "learning":
            text = f"""LEARNING
--------
Display: {display}
Learning ID: {data.get('learning_id', '')}
Source Type: {data.get('source_type', '')}
Source ID: {data.get('source_id', '')}
Created: {safe_dt(data.get('created_at'))}
Approved: {data.get('approved', False)}

Insights:
{bullet_lines(data.get('insights'), limit=4, formatter=lambda i: first_sentence(to_dict(i).get('detail')))}

Patterns:
{bullet_lines(data.get('reusable_patterns'), limit=4, formatter=lambda p: to_dict(p).get('pattern', ''))}

Prompt Suggestions:
{bullet_lines(data.get('suggested_prompt_updates'), limit=4, formatter=lambda s: first_sentence(to_dict(s).get('suggestion')))}
"""
            self.details_output.update(text)
            return

        self.details_output.update(json.dumps(data, indent=2))

    def render_risk(self, node_type: str, data: Dict[str, Any]):
        if node_type == "review":
            weaknesses = to_list(to_dict(data.get("result")).get("weaknesses"))
            high = sum(1 for w in weaknesses if str(to_dict(w).get("severity", "")).lower() == "high")
            med = sum(1 for w in weaknesses if str(to_dict(w).get("severity", "")).lower() == "medium")
            low = sum(1 for w in weaknesses if str(to_dict(w).get("severity", "")).lower() == "low")
            top = first_sentence(to_dict(weaknesses[0]).get("description")) if weaknesses else "None"
            status = "READY FOR RECONCILIATION" if len(weaknesses) == 0 else "NOT READY"
            self.risk_output.update(f"Risk summary\n- High: {high}\n- Medium: {med}\n- Low: {low}\n- Top issue: {top}\n- Status: {status}")
            return

        if node_type == "reconciliation":
            merged = to_list(data.get("merged_weaknesses"))
            high = sum(1 for w in merged if str(to_dict(w).get("severity", "")).lower() == "high")
            categories = ", ".join(friendly_category(to_dict(w).get("category")) for w in merged[:4]) or "None"
            status = "READY FOR PROPOSAL" if merged else "LOW RISK"
            self.risk_output.update(f"Risk summary\n- Merged areas: {len(merged)}\n- High severity groups: {high}\n- Categories: {categories}\n- Status: {status}")
            return

        if node_type == "proposal":
            recs = to_list(data.get("recommendations"))
            high = sum(1 for r in recs if str(to_dict(r).get("priority", "")).lower() == "high")
            self.risk_output.update(f"Risk summary\n- Recommendations: {len(recs)}\n- High priority: {high}\n- Status: DELIVERY ACTIONS REQUIRED")
            return

        if node_type == "learning":
            insights = to_list(data.get("insights"))
            patterns = to_list(data.get("reusable_patterns"))
            self.risk_output.update(f"Learning summary\n- Insights: {len(insights)}\n- Patterns: {len(patterns)}\n- Status: READY TO FEED BACK INTO PROMPTS")
            return

        self.risk_output.update("Risk summary will appear here when a Review, Reconciliation, Proposal, or Learning node is selected.")

    def render_compare(self):
        if len(self.compare_nodes) != 2:
            return

        (type_a, data_a, display_a), (type_b, data_b, display_b) = self.compare_nodes
        if type_a != type_b:
            self.compare_output.update("Cannot compare different node types")
            return

        if type_a == "review":
            a_result = to_dict(data_a.get("result"))
            b_result = to_dict(data_b.get("result"))
            a_weak = to_list(a_result.get("weaknesses"))
            b_weak = to_list(b_result.get("weaknesses"))
            a_cats = {to_dict(w).get("category") for w in a_weak}
            b_cats = {to_dict(w).get("category") for w in b_weak}
            only_a = ", ".join(sorted(friendly_category(x) for x in a_cats - b_cats)) or "None"
            only_b = ", ".join(sorted(friendly_category(x) for x in b_cats - a_cats)) or "None"
            self.compare_output.update(
                f"Compare Reviews\nSelected option 1: {display_a}\nSelected option 2: {display_b}\n\n"
                f"A count: {len(a_weak)}\nB count: {len(b_weak)}\n"
                f"Only in A: {only_a}\nOnly in B: {only_b}\n\n"
                f"A assessment: {to_dict(a_result.get('summary')).get('overall_assessment', '')}\n\n"
                f"B assessment: {to_dict(b_result.get('summary')).get('overall_assessment', '')}"
            )
            return

        if type_a == "proposal":
            a_summary = to_dict(data_a.get("summary"))
            b_summary = to_dict(data_b.get("summary"))
            self.compare_output.update(
                f"Compare Proposals\nSelected option 1: {display_a}\nSelected option 2: {display_b}\n\n"
                f"A: {a_summary.get('executive_summary', '')}\n\n"
                f"B: {b_summary.get('executive_summary', '')}"
            )
            return

        if type_a == "learning":
            a_ins = bullet_lines(data_a.get("insights"), limit=3, formatter=lambda i: first_sentence(to_dict(i).get('detail')))
            b_ins = bullet_lines(data_b.get("insights"), limit=3, formatter=lambda i: first_sentence(to_dict(i).get('detail')))
            self.compare_output.update(
                f"Compare Learning\nSelected option 1: {display_a}\nSelected option 2: {display_b}\n\nA insights:\n{a_ins}\n\nB insights:\n{b_ins}"
            )
            return

        self.compare_output.update("Compare is supported for Review, Proposal, and Learning only.")


if __name__ == "__main__":
    ContextaV72().run()
