from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree
from textual.containers import Horizontal
from textual.reactive import reactive

import requests
import json

BASE_URL = "http://localhost:5000"


# -------------------------
# API helpers
# -------------------------

def get_versions():
    return requests.get(f"{BASE_URL}/versions").json()

def get_reviews():
    return requests.get(f"{BASE_URL}/reviews").json()

def get_proposals():
    return requests.get(f"{BASE_URL}/proposal").json()


# -------------------------
# UI Components
# -------------------------

class DetailPanel(Static):
    content = reactive("Select an item")

    def update_content(self, text):
        self.content = text
        self.update(text)


# -------------------------
# Main App
# -------------------------

class ContextaTUI(App):

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #left {
        width: 40%;
        border-right: solid gray;
    }

    #right {
        width: 60%;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):
            self.tree = Tree("Contexta Artifacts", id="left")
            self.detail = DetailPanel("Select a node", id="right")

            yield self.tree
            yield self.detail

        yield Footer()

    def on_mount(self):
        self.load_tree()

    # -------------------------
    # Load Data Into Tree
    # -------------------------

    def load_tree(self):
        versions = get_versions()
        reviews = get_reviews()
        proposals = get_proposals()

        root = self.tree.root
        root.expand()

        for v in versions:
            node_version = root.add(f"Version: {v['version_id']}", data=("version", v))

            # Reviews under version
            for r in reviews:
                if r.get("version_id") == v["version_id"]:
                    node_review = node_version.add(
                        f"Review: {r['review_id']}",
                        data=("review", r)
                    )

            # Proposal under version
            for p in proposals:
                if p.get("source_type") == "reconciliation":
                    node_version.add(
                        f"Proposal: {p['proposal_id']}",
                        data=("proposal", p)
                    )

        self.tree.focus()

    # -------------------------
    # Selection handler
    # -------------------------

    def on_tree_node_selected(self, event):
        node = event.node

        if not node.data:
            return

        node_type, data = node.data

        if node_type == "version":
            text = f"""
VERSION
-------
ID: {data.get('version_id')}
Project: {data.get('project_id')}
"""
        elif node_type == "review":
            summary = data.get("result", {}).get("summary", {})
            text = f"""
REVIEW
------
ID: {data.get("review_id")}

Summary:
{summary.get("overall_assessment", "N/A")}
"""
        elif node_type == "proposal":
            summary = data.get("summary", {})
            text = f"""
PROPOSAL
--------
ID: {data.get("proposal_id")}

Executive Summary:
{summary.get("executive_summary", "")}
"""
        else:
            text = json.dumps(data, indent=2)

        self.detail.update_content(text)


if __name__ == "__main__":
    ContextaTUI().run()
