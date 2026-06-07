# v7_1_contexta_tui_full.py
# FULL UPGRADE: v6 + version-aware naming + grouped (Option B)

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static, Input, Button, Label
from textual.containers import Horizontal, Vertical
import requests
import json
from typing import List, Dict

BASE_URL = "http://localhost:5000"

# ---------------- API ----------------

def api_get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}")
        return r.json() if r.ok else []
    except:
        return []

# ---------------- SAFE HELPERS ----------------

def to_dict(v):
    return v if isinstance(v, dict) else {}


def to_list(v):
    return v if isinstance(v, list) else []

# ---------------- RELATIONSHIPS ----------------

def build_relationships(reviews, recons, proposals, learning):
    review_by_version = {}
    for r in reviews:
        review_by_version.setdefault(r['version_id'], []).append(r)

    recon_by_version = {}
    for rc in recons:
        ids = rc.get("review_ids", [])
        if ids:
            vid = next((r['version_id'] for r in reviews if r['review_id'] == ids[0]), None)
            if vid:
                recon_by_version.setdefault(vid, []).append(rc)

    proposal_by_version = {}
    for p in proposals:
        rcid = p.get("source_id")
        rc = next((x for x in recons if x['recon_id'] == rcid), None)
        if rc:
            vid = next((r['version_id'] for r in reviews if r['review_id'] in rc.get("review_ids", [])), None)
            if vid:
                proposal_by_version.setdefault(vid, []).append(p)

    learning_by_version = {}
    for l in learning:
        pid = l.get("source_id")
        prop = next((x for x in proposals if x['proposal_id'] == pid), None)
        if prop:
            rc = next((x for x in recons if x['recon_id'] == prop.get("source_id")), None)
            if rc:
                vid = next((r['version_id'] for r in reviews if r['review_id'] in rc.get("review_ids", [])), None)
                if vid:
                    learning_by_version.setdefault(vid, []).append(l)

    return review_by_version, recon_by_version, proposal_by_version, learning_by_version

# ---------------- NAMING (Option 2) ----------------

def review_name(v, idx, personas):
    tag = "Base" if not personas else "+".join([p[:3].capitalize() for p in personas])
    return f"R[{v[:2]}_{tag}_{idx:02d}]"


def recon_name(v, review_ids):
    tokens = ["R" + str(i+1).zfill(2) for i in range(len(review_ids))]
    return f"Recon[{v[:2]}_{'_'.join(tokens)}]"


def proposal_name(v, idx):
    return f"Prop[{v[:2]}_Rec{idx:02d}]"


def learning_name(v, idx):
    return f"Learn[{v[:2]}_Prop{idx:02d}]"

# ---------------- UI ----------------

class ContextaV71(App):

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #left { width: 35%; }
    #right { width: 65%; }
    #details { height: 60%; }
    #compare { height: 40%; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield Tree("Contexta Pipeline", id="tree")
            with Vertical(id="right"):
                yield Static("Details", id="details")
                yield Static("Compare", id="compare")
        yield Footer()

    def on_mount(self):
        self.tree_widget = self.query_one("#tree", Tree)
        self.details = self.query_one("#details", Static)
        self.compare = self.query_one("#compare", Static)
        self.compare_mode = False
        self.compare_nodes = []
        self.load_tree()

    def load_tree(self):
        root = self.tree_widget.root
        root.remove_children()
        root.expand()

        projects = api_get("/projects")
        versions = api_get("/versions")
        reviews = api_get("/reviews")
        recons = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning = api_get("/learning")

        review_map, recon_map, proposal_map, learning_map = build_relationships(
            reviews, recons, proposals, learning
        )

        for p in projects:
            pnode = root.add(f"📁 {p.get('name')}", data=("project", p))

            for v in [x for x in versions if x['project_id'] == p['project_id']]:
                vid = v['version_id']
                vnode = pnode.add(f"📦 {vid[:6]}", data=("version", v))

                # Reviews
                rgroup = vnode.add("📝 Reviews")
                for i, r in enumerate(review_map.get(vid, []), 1):
                    rgroup.add(review_name(vid, i, r.get('personas')), data=("review", r))

                # Recon
                rcgroup = vnode.add("🔗 Reconciliation")
                for i, rc in enumerate(recon_map.get(vid, []), 1):
                    rcgroup.add(recon_name(vid, rc.get('review_ids', [])), data=("recon", rc))

                # Proposal
                pgroup = vnode.add("📄 Proposals")
                for i, pr in enumerate(proposal_map.get(vid, []), 1):
                    pgroup.add(proposal_name(vid, i), data=("proposal", pr))

                # Learning
                lgroup = vnode.add("📘 Learning")
                for i, l in enumerate(learning_map.get(vid, []), 1):
                    lgroup.add(learning_name(vid, i), data=("learning", l))

        self.tree_widget.focus()

    def on_tree_node_selected(self, event):
        node = event.node
        if not node.data:
            return

        node_type, data = node.data
        self.details.update(json.dumps(data, indent=2))

        if self.compare_mode:
            self.compare_nodes.append(data)
            if len(self.compare_nodes) == 2:
                self.run_compare()
                self.compare_nodes = []
                self.compare_mode = False

    def run_compare(self):
        a, b = self.compare_nodes
        a_w = to_list(to_dict(a.get("result")).get("weaknesses"))
        b_w = to_list(to_dict(b.get("result")).get("weaknesses"))

        self.compare.update(f"A weaknesses: {len(a_w)}\nB weaknesses: {len(b_w)}")


if __name__ == "__main__":
    ContextaV71().run()
