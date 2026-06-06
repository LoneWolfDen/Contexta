from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree
from textual.containers import Horizontal
from textual.binding import Binding

import requests
import json

BASE_URL = "http://localhost:5000"


# ---------------- API HELPERS ----------------

def api_get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}")
        return r.json() if r.ok else []
    except:
        return []


def api_post(path, payload):
    r = requests.post(f"{BASE_URL}{path}", json=payload)
    if not r.ok:
        return None
    return r.json()


# ---------------- UI PANEL ----------------

class DetailPanel(Static):
    def show(self, text):
        self.update(text)


# ---------------- MAIN APP ----------------

class ContextaTUI(App):

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "run_review", "Run Review"),
        Binding("i", "run_iteration", "Run Iteration"),
        Binding("c", "compare_mode", "Compare"),
        Binding("p", "run_proposal", "Proposal"),
        Binding("o", "run_recon", "Reconcile")
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            yield Tree("Contexta Flow", id="tree")
            yield DetailPanel("Select node", id="detail")

        yield Footer()

    def on_mount(self):
        self.tree = self.query_one("#tree", Tree)
        self.detail = self.query_one("#detail", DetailPanel)

        self.compare_nodes = []
        self.compare_active = False

        self.load_tree()

    # ---------------- LOAD TREE ----------------

    def load_tree(self):
        self.tree.root.remove_children()
        root = self.tree.root
        root.expand()

        projects = api_get("/projects")
        versions = api_get("/versions")
        reviews = api_get("/reviews")
        recons = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning = api_get("/learning")

        for p in projects:
            p_node = root.add(
                f"📁 {p.get('name')}",
                data=("project", p)
            )

            p_versions = [v for v in versions if v.get("project_id") == p["project_id"]]

            for v in p_versions:
                v_node = p_node.add(
                    f"📦 Version {v.get('version_id')[:6]}",
                    data=("version", v)
                )

                v_reviews = [r for r in reviews if r.get("version_id") == v["version_id"]]

                for r in v_reviews:
                    personas = r.get("personas") or r.get("result", {}).get("personas", [])
                    label = f"📝 Review {r['review_id'][:6]}"
                    if personas:
                        label += f" ({', '.join(personas)})"

                    v_node.add(label, data=("review", r))

                for rec in recons:
                    if any(rid in rec.get("review_ids", []) for rid in [rv.get("review_id") for rv in v_reviews]):
                        v_node.add(
                            f"🔗 Recon {rec['recon_id'][:6]}",
                            data=("recon", rec)
                        )

                for prop in proposals:
                    if prop.get("source_type") == "reconciliation":
                        v_node.add(
                            f"📄 Proposal {prop['proposal_id'][:6]}",
                            data=("proposal", prop)
                        )

                        related_learning = [
                            l for l in learning
                            if l.get("source_id") == prop["proposal_id"]
                        ]

                        for l in related_learning:
                            v_node.add(
                                f"📘 Learning {l['learning_id'][:6]}",
                                data=("learning", l)
                            )

    # ---------------- NODE SELECT ----------------

    def on_tree_node_selected(self, event):
        node = event.node

        if not node.data:
            return

        if self.compare_active:
            self.compare_nodes.append(node)

            if len(self.compare_nodes) == 2:
                self.show_compare()
                self.compare_nodes = []
                self.compare_active = False
            return

        self.show_detail(node.data)

    # ---------------- DETAIL VIEW ----------------

    def show_detail(self, node_data):
        node_type, data = node_data

        if node_type == "review":
            summary = data.get("result", {}).get("summary", {})
            txt = f"""
REVIEW {data.get("review_id")}

{summary.get("overall_assessment", "")}
"""
        elif node_type == "proposal":
            txt = data.get("summary", {}).get("executive_summary", "")
        elif node_type == "recon":
            txt = json.dumps(data, indent=2)
        elif node_type == "learning":
            insights = [i.get("detail") for i in data.get("insights", [])]
            txt = "\n".join(insights[:3])
        else:
            txt = json.dumps(data, indent=2)

        self.detail.show(txt)

    # ---------------- ACTIONS ----------------

    def action_run_review(self):
        node = self.tree.cursor_node
        if not node or node.data[0] != "version":
            self.notify("Select a version first")
            return

        version_id = node.data[1]["version_id"]
        result = api_post("/reviews", {"version_id": version_id})

        self.notify("Review created" if result else "Error")
        self.load_tree()

    def action_run_iteration(self):
        node = self.tree.cursor_node
        if not node or node.data[0] != "version":
            self.notify("Select a version first")
            return

        version_id = node.data[1]["version_id"]

        result = api_post("/reviews", {
            "version_id": version_id,
            "personas": ["Architect", "Security"],
            "user_context": "Focus on risks"
        })

        self.notify("Iteration created" if result else "Error")
        self.load_tree()

    def action_run_recon(self):
        reviews = api_get("/reviews")
        if len(reviews) < 2:
            self.notify("Need at least 2 reviews")
            return

        ids = [reviews[-1]["review_id"], reviews[-2]["review_id"]]
        result = api_post("/reconciliation", {"review_ids": ids})

        self.notify("Reconciliation created" if result else "Error")
        self.load_tree()

    def action_run_proposal(self):
        recons = api_get("/reconciliation")
        if not recons:
            self.notify("No reconciliation found")
            return

        recon_id = recons[-1]["recon_id"]
        result = api_post("/proposal", {"recon_id": recon_id})

        self.notify("Proposal created" if result else "Error")
        self.load_tree()

    def action_compare_mode(self):
        self.compare_active = True
        self.compare_nodes = []
        self.notify("Select 2 nodes to compare")

    # ---------------- COMPARE ----------------

    def show_compare(self):
        n1 = self.compare_nodes[0].data
        n2 = self.compare_nodes[1].data

        if not n1 or not n2 or n1[0] != n2[0]:
            self.detail.show("Cannot compare different types")
            return

        if n1[0] == "review":
            a = n1[1].get("result", {}).get("summary", {}).get("overall_assessment", "")
            b = n2[1].get("result", {}).get("summary", {}).get("overall_assessment", "")

            txt = f"""
=== COMPARE REVIEWS ===

--- A ---
{a}

--- B ---
{b}
"""
        else:
            txt = "Compare not implemented for this type"

        self.detail.show(txt)


if __name__ == "__main__":
    ContextaTUI().run()
