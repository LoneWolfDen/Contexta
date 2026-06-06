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

def safe_get(path: str):
    res = requests.get(f"{BASE_URL}{path}")
    if not res.ok:
        return []
    return res.json()


def get_projects():
    return safe_get("/projects")


def get_versions():
    return safe_get("/versions")


def get_reviews():
    return safe_get("/reviews")


def get_proposals():
    return safe_get("/proposal")


def get_learning():
    return safe_get("/learning")


# -------------------------
# UI Components
# -------------------------

class DetailPanel(Static):
    content = reactive("Select an item from the left panel")

    def update_content(self, text: str):
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
        yield Header(show_clock=True)

        with Horizontal(id="main"):
            yield Tree("Contexta Artifact Flow", id="left")
            yield DetailPanel("Select a node", id="right")

        yield Footer()

    def on_mount(self):
        self.artifact_tree = self.query_one("#left", Tree)
        self.detail_panel = self.query_one("#right", DetailPanel)
        self.load_tree()

    # -------------------------
    # Build left-side tree
    # -------------------------

    def load_tree(self):
        projects = get_projects()
        versions = get_versions()
        reviews = get_reviews()
        proposals = get_proposals()
        learning_items = get_learning()

        root = self.artifact_tree.root
        root.remove_children()
        root.label = "Contexta Artifact Flow"
        root.expand()

        # Group by project → version → review/proposal/learning
        for project in projects:
            project_id = project.get("project_id", "")
            project_name = project.get("name", project_id)

            project_node = root.add(
                f"Project: {project_name}",
                data=("project", project)
            )

            project_versions = [v for v in versions if v.get("project_id") == project_id]

            for version in project_versions:
                version_id = version.get("version_id", "")
                version_node = project_node.add(
                    f"Version: {version_id}",
                    data=("version", version)
                )

                version_reviews = [r for r in reviews if r.get("version_id") == version_id]

                # Reviews
                for review in version_reviews:
                    review_node = version_node.add(
                        f"Review: {review.get('review_id', '')}",
                        data=("review", review)
                    )

                    personas = review.get("result", {}).get("personas", []) or review.get("personas", [])
                    if personas:
                        review_node.add(
                            f"Personas: {', '.join(personas)}",
                            data=("review_meta", {"personas": personas, "review_id": review.get("review_id", "")})
                        )

                # Proposals (linked by references/source)
                for proposal in proposals:
                    refs = proposal.get("source_refs", [])
                    proposal_source_type = proposal.get("source_type", "")
                    if proposal_source_type == "reconciliation":
                        # We do not have direct version linkage here, so just attach proposals under project if source refs intersect reviews in this version
                        review_ids = {r.get("review_id") for r in version_reviews}
                        if any(ref in review_ids for ref in refs):
                            proposal_node = version_node.add(
                                f"Proposal: {proposal.get('proposal_id', '')}",
                                data=("proposal", proposal)
                            )

                            # Learning items related to this proposal
                            related_learning = [
                                l for l in learning_items
                                if l.get("source_type") == "proposal" and l.get("source_id") == proposal.get("proposal_id")
                            ]

                            for learning in related_learning:
                                proposal_node.add(
                                    f"Learning: {learning.get('learning_id', '')}",
                                    data=("learning", learning)
                                )

        self.artifact_tree.focus()

    # -------------------------
    # Selection handler
    # -------------------------

    def on_tree_node_selected(self, event):
        node = event.node

        if not node.data:
            return

        node_type, data = node.data

        if node_type == "project":
            text = f"""
PROJECT
-------
Name: {data.get("name", "")}
Project ID: {data.get("project_id", "")}
Created: {data.get("created_at", "")}
"""
        elif node_type == "version":
            summary = data.get("version_summary", {})
            text = f"""
VERSION
-------
Version ID: {data.get("version_id", "")}
Project ID: {data.get("project_id", "")}

Version Summary:
Client Ask: {summary.get("client_ask", "")}
Architecture: {summary.get("architecture_understanding", "")}
Missing Info: {", ".join(summary.get("missing_information", []))}
"""
        elif node_type == "review":
            result = data.get("result", {})
            summary = result.get("summary", {})
            weaknesses = result.get("weaknesses", [])
            personas = result.get("personas", []) or data.get("personas", [])

            text = f"""
REVIEW
------
Review ID: {data.get("review_id", "")}
Version ID: {data.get("version_id", "")}
Status: {data.get("status", "")}
Personas: {", ".join(personas) if personas else "None"}

Overall Assessment:
{summary.get("overall_assessment", "")}

Weakness Count: {len(weaknesses)}
"""
        elif node_type == "review_meta":
            text = f"""
REVIEW PERSONAS
---------------
Review ID: {data.get("review_id", "")}
Personas: {", ".join(data.get("personas", []))}
"""
        elif node_type == "proposal":
            summary = data.get("summary", {})
            recommendations = data.get("recommendations", [])

            text = f"""
PROPOSAL
--------
Proposal ID: {data.get("proposal_id", "")}
Source Type: {data.get("source_type", "")}
Source ID: {data.get("source_id", "")}

Executive Summary:
{summary.get("executive_summary", "")}

Recommended Solution:
{summary.get("recommended_solution", "")}

Recommendations Count: {len(recommendations)}
"""
        elif node_type == "learning":
            insights = data.get("insights", [])
            patterns = data.get("reusable_patterns", [])

            insight_lines = "\n".join(
                f"- {i.get('detail', '')}" for i in insights[:3]
            ) or "None"

            pattern_lines = "\n".join(
                f"- {p.get('pattern', '')}" for p in patterns[:3]
            ) or "None"

            text = f"""
LEARNING
--------
Learning ID: {data.get("learning_id", "")}
Source Type: {data.get("source_type", "")}
Source ID: {data.get("source_id", "")}
Approved: {data.get("approved", False)}

Insights:
{insight_lines}

Reusable Patterns:
{pattern_lines}
"""
        else:
            text = json.dumps(data, indent=2)

        self.detail_panel.update_content(text)


if __name__ == "__main__":
    ContextaTUI().run()
