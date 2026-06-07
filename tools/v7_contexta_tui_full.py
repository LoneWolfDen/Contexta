# v7_contexta_tui_full.py
# Full version-aware grouped TUI (Option B)

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static
from textual.containers import Horizontal
import requests
import json

BASE_URL = "http://localhost:5000"

# ---------------- API ----------------

def api_get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}")
        return r.json() if r.ok else []
    except:
        return []

# ---------------- Relationship Builder ----------------

def build_index(reviews, recons, proposals, learning):
    review_by_version = {}
    for r in reviews:
        review_by_version.setdefault(r['version_id'], []).append(r)

    recon_by_version = {}
    for rc in recons:
        vid = None
        if rc.get('review_ids'):
            vid = next((r['version_id'] for r in reviews if r['review_id'] == rc['review_ids'][0]), None)
        if vid:
            recon_by_version.setdefault(vid, []).append(rc)

    proposal_by_recon = {p['proposal_id']: p for p in proposals}
    proposal_by_version = {}
    for p in proposals:
        rid = p.get('source_id')
        recon = next((r for r in recons if r['recon_id'] == rid), None)
        if recon:
            vid = next((r['version_id'] for r in reviews if r['review_id'] in recon.get('review_ids', [])), None)
            if vid:
                proposal_by_version.setdefault(vid, []).append(p)

    learning_by_version = {}
    for l in learning:
        pid = l.get('source_id')
        prop = next((p for p in proposals if p['proposal_id'] == pid), None)
        if prop:
            recon = next((r for r in recons if r['recon_id'] == prop.get('source_id')), None)
            if recon:
                vid = next((r['version_id'] for r in reviews if r['review_id'] in recon.get('review_ids', [])), None)
                if vid:
                    learning_by_version.setdefault(vid, []).append(l)

    return review_by_version, recon_by_version, proposal_by_version, learning_by_version

# ---------------- Naming ----------------

def review_name(v, idx, personas):
    tag = 'Base' if not personas else '+'.join([p[:3].capitalize() for p in personas])
    return f"R[{v[:4]}_{tag}_{idx}]"


def recon_name(v, review_ids):
    r = '_'.join([rid[:3] for rid in review_ids])
    return f"Recon[{v[:4]}_{r}]"


def prop_name(v):
    return f"Prop[{v[:4]}]"


def learn_name(v):
    return f"Learn[{v[:4]}]"

# ---------------- APP ----------------

class ContextaV7(App):

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Tree("Contexta", id="tree")
            yield Static("Details", id="details")
        yield Footer()

    def on_mount(self):
        self.tree = self.query_one("#tree")
        self.details = self.query_one("#details")
        self.load_tree()

    def load_tree(self):
        root = self.tree.root
        root.remove_children()
        root.expand()

        projects = api_get("/projects")
        versions = api_get("/versions")
        reviews = api_get("/reviews")
        recons = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning = api_get("/learning")

        review_by_version, recon_by_version, proposal_by_version, learning_by_version = build_index(
            reviews, recons, proposals, learning)

        for p in projects:
            pnode = root.add(f"📁 {p['name']}", data=("project", p))

            for v in [x for x in versions if x['project_id'] == p['project_id']]:
                vid = v['version_id']
                vnode = pnode.add(f"📦 {vid[:6]}", data=("version", v))

                # Reviews
                rgroup = vnode.add("📝 Reviews")
                for i, r in enumerate(review_by_version.get(vid, []), 1):
                    rgroup.add(review_name(vid, i, r.get('personas')), data=("review", r))

                # Recon
                rcgroup = vnode.add("🔗 Reconciliation")
                for rc in recon_by_version.get(vid, []):
                    rcgroup.add(recon_name(vid, rc.get('review_ids', [])), data=("recon", rc))

                # Proposal
                pgroup = vnode.add("📄 Proposals")
                for pr in proposal_by_version.get(vid, []):
                    pgroup.add(prop_name(vid), data=("proposal", pr))

                # Learning
                lgroup = vnode.add("📘 Learning")
                for l in learning_by_version.get(vid, []):
                    lgroup.add(learn_name(vid), data=("learning", l))

        self.tree.focus()

    def on_tree_node_selected(self, event):
        node = event.node
        if not node.data:
            return
        _, data = node.data
        self.details.update(json.dumps(data, indent=2))


if __name__ == "__main__":
    ContextaV7().run()
