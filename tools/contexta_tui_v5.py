from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Tree, Static, Input, Button
)
from textual.containers import Horizontal, Vertical
from textual.binding import Binding

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


def api_post(path, payload):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=payload)
        return r.json() if r.ok else None
    except:
        return None


# ---------------- MAIN APP ----------------

class ContextaConsole(App):

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("l", "refresh", "Refresh"),
        Binding("c", "compare_toggle", "Compare"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #tree {
        width: 30%;
        border-right: solid #666;
    }

    #right {
        width: 70%;
    }

    #detail {
        height: 1fr;
        padding: 1;
    }

    #tabs {
        height: 3;
        border-top: solid #444;
    }

    #input_panel {
        height: 6;
        border-top: solid #666;
        padding: 1;
    }

    Input {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:

        yield Header()

        # MAIN SPLIT
        with Horizontal(id="main"):

            yield Tree("Contexta Pipeline", id="tree")

            with Vertical(id="right"):

                yield Static("Select a node", id="detail")

                # Tabs placeholder
                yield Static("[Details]   [Compare]   [Run]", id="tabs")

                # INPUT PANEL
                with Vertical(id="input_panel"):

                    yield Static("Run Controls")

                    yield Input(placeholder="Personas (e.g. Architect,Security)", id="personas")
                    yield Input(placeholder="User Context", id="context")

                    yield Horizontal(
                        Button("Run Review", id="run_review"),
                        Button("Run Iteration", id="run_iter"),
                        Button("Reconcile", id="run_recon"),
                        Button("Proposal", id="run_prop"),
                    )

        yield Footer()

    # ---------------- INIT ----------------

    def on_mount(self):

        self.tree = self.query_one("#tree", Tree)
        self.detail = self.query_one("#detail", Static)

        self.personas_input = self.query_one("#personas", Input)
        self.context_input = self.query_one("#context", Input)

        self.compare_mode = False
        self.compare_nodes = []

        self.load_tree()

    # ---------------- LOAD TREE ----------------

    def load_tree(self):

        root = self.tree.root
        root.remove_children()
        root.expand()

        versions = api_get("/versions")
        reviews = api_get("/reviews")
        recons = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning = api_get("/learning")

        for v in versions:

            v_node = root.add(
                f"📦 Version {v['version_id'][:6]}",
                data=("version", v)
            )

            v_reviews = [r for r in reviews if r.get("version_id") == v["version_id"]]

            for r in v_reviews:
                personas = r.get("personas") or r.get("result", {}).get("personas", [])
                label = f"Review {r['review_id'][:6]}"
                if personas:
                    label += f" ({','.join(personas)})"

                v_node.add(label, data=("review", r))

            for rec in recons:
                if any(r["review_id"] in rec.get("review_ids", []) for r in v_reviews):
                    v_node.add(
                        f"Recon {rec['recon_id'][:6]}",
                        data=("recon", rec)
                    )

            for p in proposals:
                if p.get("source_type") == "reconciliation":
                    v_node.add(
                        f"Proposal {p['proposal_id'][:6]}",
                        data=("proposal", p)
                    )

    # ---------------- SELECT ----------------

    def on_tree_node_selected(self, event):

        node = event.node

        if not node.data:
            return

        if self.compare_mode:
            self.compare_nodes.append(node)

            if len(self.compare_nodes) == 2:
                self.run_compare()
                self.compare_nodes = []
                self.compare_mode = False
            return

        self.show_detail(node.data)

    # ---------------- DETAIL ----------------

    def show_detail(self, node_data):

        t, data = node_data

        if t == "review":
            summary = data.get("result", {}).get("summary", {})
            txt = summary.get("overall_assessment", "No summary")
        elif t == "proposal":
            txt = data.get("summary", {}).get("executive_summary", "")
        elif t == "version":
            txt = json.dumps(data, indent=2)
        else:
            txt = json.dumps(data, indent=2)

        self.detail.update(txt)

    # ---------------- BUTTON ACTIONS ----------------

    def on_button_pressed(self, event):

        node = self.tree.cursor_node

        if not node or not node.data:
            return

        t, data = node.data

        personas = [p.strip() for p in self.personas_input.value.split(",") if p.strip()]
        context = self.context_input.value

        # REVIEW
        if event.button.id == "run_review" and t == "version":
            api_post("/reviews", {"version_id": data["version_id"]})

        # ITERATION (✅ NOW TAKES INPUT)
        elif event.button.id == "run_iter" and t == "version":
            api_post("/reviews", {
                "version_id": data["version_id"],
                "personas": personas,
                "user_context": context
            })

        # RECON
        elif event.button.id == "run_recon":
            reviews = api_get("/reviews")
            if len(reviews) >= 2:
                api_post("/reconciliation", {
                    "review_ids": [reviews[-1]["review_id"], reviews[-2]["review_id"]]
                })

        # PROPOSAL
        elif event.button.id == "run_prop":
            recons = api_get("/reconciliation")
            if recons:
                api_post("/proposal", {"recon_id": recons[-1]["recon_id"]})

        self.load_tree()

    # ---------------- COMPARE ----------------

    def action_compare_toggle(self):
        self.compare_mode = True
        self.compare_nodes = []
        self.detail.update("Select 2 reviews to compare")

    def run_compare(self):

        a = self.compare_nodes[0].data
        b = self.compare_nodes[1].data

        if not a or not b or a[0] != b[0]:
            self.detail.update("Invalid compare")
            return

        if a[0] == "review":

            a_txt = a[1].get("result", {}).get("summary", {}).get("overall_assessment", "")
            b_txt = b[1].get("result", {}).get("summary", {}).get("overall_assessment", "")

            self.detail.update(f"""
=== REVIEW A ===
{a_txt}

--------------------

=== REVIEW B ===
{b_txt}
""")

    # ---------------- REFRESH ----------------

    def action_refresh(self):
        self.load_tree()


if __name__ == "__main__":
    ContextaConsole().run()
