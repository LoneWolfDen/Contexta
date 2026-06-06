from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree
from textual.containers import Horizontal
from textual.binding import Binding

import requests
import json

BASE_URL = "http://localhost:5000"


# ---------------- API HELPERS ----------------

def api_get(path: str):
    try:
        resp = requests.get(f"{BASE_URL}{path}")
        if not resp.ok:
            return []
        return resp.json()
    except Exception:
        return []


def api_post(path: str, payload: dict):
    try:
        resp = requests.post(f"{BASE_URL}{path}", json=payload)
        if not resp.ok:
            return None
        return resp.json()
    except Exception:
        return None


# ---------------- DETAIL PANEL ----------------

class DetailPanel(Static):
    def show_text(self, text: str):
        self.update(text)


# ---------------- MAIN APP ----------------

class ContextaTUI(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "run_review", "Run Review"),
        Binding("i", "run_iteration", "Run Iteration"),
        Binding("o", "run_reconciliation", "Run Reconciliation"),
        Binding("p", "run_proposal", "Run Proposal"),
        Binding("c", "toggle_compare", "Compare"),
        Binding("l", "refresh_tree", "Refresh"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #artifact_tree {
        width: 40%;
        border-right: solid gray;
    }

    #detail_panel {
        width: 60%;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main"):
            yield Tree("Contexta Flow", id="artifact_tree")
            yield DetailPanel("Select a node from the left panel", id="detail_panel")

        yield Footer()

    def on_mount(self):
        self.artifact_tree = self.query_one("#artifact_tree", Tree)
        self.detail_panel = self.query_one("#detail_panel", DetailPanel)

        self.compare_mode = False
        self.compare_selection = []

        self.load_tree()

    # ---------------- TREE LOADING ----------------

    def load_tree(self):
        projects = api_get("/projects")
        versions = api_get("/versions")
        reviews = api_get("/reviews")
        reconciliations = api_get("/reconciliation")
        proposals = api_get("/proposal")
        learning_items = api_get("/learning")

        root = self.artifact_tree.root
        root.remove_children()
        root.label = "Contexta Flow"
        root.expand()

        for project in projects:
            project_id = project.get("project_id", "")
            project_name = project.get("name", project_id)

            project_node = root.add(
                f"📁 Project: {project_name}",
                data=("project", project)
            )

            project_versions = [v for v in versions if v.get("project_id") == project_id]

            for version in project_versions:
                version_id = version.get("version_id", "")
                version_node = project_node.add(
                    f"📦 Version: {version_id[:8]}",
                    data=("version", version)
                )

                version_reviews = [r for r in reviews if r.get("version_id") == version_id]
                review_ids = [r.get("review_id") for r in version_reviews]

                # Reviews under version
                reviews_node = version_node.add("📝 Reviews", data=None)

                for review in version_reviews:
                    personas = review.get("personas") or review.get("result", {}).get("personas", [])
                    label = f"Review: {review.get('review_id', '')[:8]}"
                    if personas:
                        label += f" ({', '.join(personas)})"

                    reviews_node.add(
                        label,
                        data=("review", review)
                    )

                # Reconciliations related to reviews
                recon_node_container = version_node.add("🔗 Reconciliation", data=None)
                matched_recons = []

                for recon in reconciliations:
                    recon_review_ids = recon.get("source_reviews") or recon.get("review_ids") or []
                    if any(rid in recon_review_ids for rid in review_ids):
                        matched_recons.append(recon)
                        recon_node_container.add(
                            f"Recon: {recon.get('recon_id', '')[:8]}",
                            data=("reconciliation", recon)
                        )

                # Proposals related to reconciliations
                proposal_node_container = version_node.add("📄 Proposals", data=None)
                matched_proposals = []

                recon_ids = [r.get("recon_id") for r in matched_recons]

                for proposal in proposals:
                    source_type = proposal.get("source_type")
                    source_id = proposal.get("source_id")

                    if source_type == "reconciliation" and source_id in recon_ids:
                        matched_proposals.append(proposal)
                        proposal_node_container.add(
                            f"Proposal: {proposal.get('proposal_id', '')[:8]}",
                            data=("proposal", proposal)
                        )

                # Learning related to proposals
                learning_node_container = version_node.add("📘 Learning", data=None)

                proposal_ids = [p.get("proposal_id") for p in matched_proposals]

                for learning in learning_items:
                    if learning.get("source_type") == "proposal" and learning.get("source_id") in proposal_ids:
                        learning_node_container.add(
                            f"Learning: {learning.get('learning_id', '')[:8]}",
                            data=("learning", learning)
                        )

        self.artifact_tree.focus()

    # ---------------- NODE SELECTION ----------------

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        node = event.node

        if not node.data:
            return

        if self.compare_mode:
            self.compare_selection.append(node)

            if len(self.compare_selection) == 2:
                self.show_compare(self.compare_selection[0], self.compare_selection[1])
                self.compare_selection = []
                self.compare_mode = False
            return

        self.show_detail(node.data)

    # ---------------- DETAIL DISPLAY ----------------

    def show_detail(self, node_data):
        node_type, data = node_data

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

Client Ask:
{summary.get("client_ask", "")}

Architecture Understanding:
{summary.get("architecture_understanding", "")}

Missing Information:
{", ".join(summary.get("missing_information", []))}
"""
        elif node_type == "review":
            result = data.get("result", {})
            summary = result.get("summary", {})
            weaknesses = result.get("weaknesses", [])
            personas = data.get("personas") or result.get("personas", [])

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
        elif node_type == "reconciliation":
            merged = data.get("merged_weaknesses", [])
            summary = data.get("summary", {})

            text = f"""
RECONCILIATION
--------------
Recon ID: {data.get("recon_id", "")}
Source Reviews: {", ".join(data.get("source_reviews", []))}
Merged Weakness Count: {len(merged)}

Consensus Findings:
{", ".join(summary.get("consensus_findings", []))}

Recommended Focus:
{chr(10).join("- " + x for x in summary.get("recommended_focus", [])[:5])}
"""
        elif node_type == "proposal":
            summary = data.get("summary", {})
            recs = data.get("recommendations", [])

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

Recommendations Count: {len(recs)}
"""
        elif node_type == "learning":
            insights = data.get("insights", [])
            patterns = data.get("reusable_patterns", [])

            insight_lines = "\n".join(f"- {i.get('detail', '')}" for i in insights[:3]) or "None"
            pattern_lines = "\n".join(f"- {p.get('pattern', '')}" for p in patterns[:3]) or "None"

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

        self.detail_panel.show_text(text)

    # ---------------- ACTIONS ----------------

    def action_run_review(self):
        node = self.artifact_tree.cursor_node
        if not node or not node.data or node.data[0] != "version":
            self.notify("Select a Version node first")
            return

        version_id = node.data[1]["version_id"]
        result = api_post("/reviews", {"version_id": version_id})

        if result:
            self.notify(f"Review created: {result.get('review_id', '')[:8]}")
            self.load_tree()
        else:
            self.notify("Failed to create review", severity="error")

    def action_run_iteration(self):
        node = self.artifact_tree.cursor_node
        if not node or not node.data or node.data[0] != "version":
            self.notify("Select a Version node first")
            return

        version_id = node.data[1]["version_id"]

        result = api_post(
            "/reviews",
            {
                "version_id": version_id,
                "personas": ["Architect", "Security"],
                "user_context": "Focus on architecture and security risks"
            }
        )

        if result:
            self.notify(f"Iteration-style review created: {result.get('review_id', '')[:8]}")
            self.load_tree()
        else:
            self.notify("Failed to create iteration review", severity="error")

    def action_run_reconciliation(self):
        node = self.artifact_tree.cursor_node
        if not node or not node.data or node.data[0] != "version":
            self.notify("Select a Version node first")
            return

        version_id = node.data[1]["version_id"]
        reviews = api_get("/reviews")
        version_reviews = [r for r in reviews if r.get("version_id") == version_id]

        if len(version_reviews) < 2:
            self.notify("Need at least 2 reviews on this version", severity="warning")
            return

        review_ids = [version_reviews[-1]["review_id"], version_reviews[-2]["review_id"]]
        result = api_post("/reconciliation", {"review_ids": review_ids})

        if result:
            self.notify(f"Reconciliation created: {result.get('recon_id', '')[:8]}")
            self.load_tree()
        else:
            self.notify("Failed to create reconciliation", severity="error")

    def action_run_proposal(self):
        node = self.artifact_tree.cursor_node
        if not node or not node.data or node.data[0] != "reconciliation":
            self.notify("Select a Reconciliation node first")
            return

        recon_id = node.data[1]["recon_id"]
        result = api_post("/proposal", {"recon_id": recon_id})

        if result:
            self.notify(f"Proposal created: {result.get('proposal_id', '')[:8]}")
            self.load_tree()
        else:
            self.notify("Failed to create proposal", severity="error")

    def action_toggle_compare(self):
        self.compare_mode = not self.compare_mode
        self.compare_selection = []
        if self.compare_mode:
            self.notify("Compare mode ON — select two nodes of the same type")
        else:
            self.notify("Compare mode OFF")

    def action_refresh_tree(self):
        self.load_tree()
        self.notify("Tree refreshed")

    # ---------------- COMPARE ----------------

    def show_compare(self, node_a, node_b):
        if not node_a.data or not node_b.data:
            self.detail_panel.show_text("Comparison failed: invalid node data")
            return

        type_a, data_a = node_a.data
        type_b, data_b = node_b.data

        if type_a != type_b:
            self.detail_panel.show_text("Cannot compare different node types")
            return

        if type_a == "review":
            a_summary = data_a.get("result", {}).get("summary", {}).get("overall_assessment", "")
            b_summary = data_b.get("result", {}).get("summary", {}).get("overall_assessment", "")

            a_weaknesses = len(data_a.get("result", {}).get("weaknesses", []))
            b_weaknesses = len(data_b.get("result", {}).get("weaknesses", []))

            text = f"""
COMPARE REVIEWS
---------------

A Review: {data_a.get("review_id", "")}
Weakness Count: {a_weaknesses}
Assessment:
{a_summary}

----------------------------------------

B Review: {data_b.get("review_id", "")}
Weakness Count: {b_weaknesses}
Assessment:
{b_summary}
"""
        elif type_a == "proposal":
            a_summary = data_a.get("summary", {}).get("executive_summary", "")
            b_summary = data_b.get("summary", {}).get("executive_summary", "")

            text = f"""
COMPARE PROPOSALS
-----------------

A Proposal: {data_a.get("proposal_id", "")}
Summary:
{a_summary}

----------------------------------------

B Proposal: {data_b.get("proposal_id", "")}
Summary:
{b_summary}
"""
        else:
            text = f"Compare not implemented for node type: {type_a}"

        self.detail_panel.show_text(text)


if __name__ == "__main__":
    ContextaTUI().run()
