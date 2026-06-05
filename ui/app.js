// ✅ AUTO detect Codespaces backend (no hardcoding needed)
const BASE_URL = window.location.origin;

// ✅ Convert technical categories to user-friendly labels
function friendlyLabel(cat) {
  if (!cat) return "Other risk";
  if (cat.includes("missing_information")) return "Missing key inputs";
  if (cat.includes("missing_security_context")) return "Security gaps";
  return cat.replaceAll("_", " ");
}

// ✅ Shorten long text to first sentence
function firstSentence(text) {
  if (!text) return "";
  const parts = text.split(".");
  return parts[0].trim() + (parts[0].trim() ? "." : "");
}

// ✅ Load latest proposal
async function loadLatestProposal() {
  const proposalBox = document.getElementById("proposal-content");
  const risksList = document.getElementById("risks-list");
  const actionsList = document.getElementById("actions-list");
  const statusBox = document.getElementById("status-message");
  const proposalBtn = document.getElementById("btn-proposal");

  try {
    proposalBtn.disabled = true;
    proposalBtn.innerText = "Loading...";
    statusBox.innerText = "Loading proposal...";
    statusBox.style.color = "green";

    const res = await fetch(`${BASE_URL}/proposal`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json"
      }
    });

    if (!res.ok) {
      throw new Error(`Proposal request failed: ${res.status}`);
    }

    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      proposalBox.innerHTML = "<p>No proposal data available.</p>";
      risksList.innerHTML = "";
      actionsList.innerHTML = "";
      statusBox.innerText = "No proposals found.";
      statusBox.style.color = "red";
      return;
    }

    const proposal = data[data.length - 1];

    renderProposal(proposal);

    statusBox.innerText = "Proposal loaded successfully.";
    statusBox.style.color = "green";

  } catch (err) {
    console.error(err);
    proposalBox.innerHTML = "<p>Could not load proposal.</p>";
    statusBox.innerText = "Failed to load proposal.";
    statusBox.style.color = "red";
  } finally {
    proposalBtn.disabled = false;
    proposalBtn.innerText = "Load Latest Proposal";
  }
}

// ✅ Load latest learning
async function loadLatestLearning() {
  const learningList = document.getElementById("learning-list");
  const statusBox = document.getElementById("status-message");
  const learningBtn = document.getElementById("btn-learning");

  try {
    learningBtn.disabled = true;
    learningBtn.innerText = "Loading...";
    statusBox.innerText = "Loading learning insights...";
    statusBox.style.color = "green";

    const res = await fetch(`${BASE_URL}/learning`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json"
      }
    });

    if (!res.ok) {
      throw new Error(`Learning request failed: ${res.status}`);
    }

    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      learningList.innerHTML = "<li>No learning data available.</li>";
      statusBox.innerText = "No learning records found.";
      statusBox.style.color = "red";
      return;
    }

    const latest = data[data.length - 1];

    renderLearning(latest);

    statusBox.innerText = "Learning insights loaded successfully.";
    statusBox.style.color = "green";

  } catch (err) {
    console.error(err);
    learningList.innerHTML = "<li>Could not load learning insights.</li>";
    statusBox.innerText = "Failed to load learning.";
    statusBox.style.color = "red";
  } finally {
    learningBtn.disabled = false;
    learningBtn.innerText = "Load Learning";
  }
}

// ✅ Render proposal (clean UX)
function renderProposal(p) {

  const proposalBox = document.getElementById("proposal-content");
  const risksList = document.getElementById("risks-list");
  const actionsList = document.getElementById("actions-list");

  // ✅ Summary
  proposalBox.innerHTML = `
    <strong>Summary:</strong>
    <p>${firstSentence(p.summary?.executive_summary)}</p>
  `;

  // ✅ Key risks (max 3)
  risksList.innerHTML = "";
  const recs = Array.isArray(p.recommendations) ? p.recommendations.slice(0, 3) : [];

  recs.forEach((r) => {
    const li = document.createElement("li");
    li.innerText = `${friendlyLabel(r.category)} (High risk)`;
    risksList.appendChild(li);
  });

  // ✅ Next actions (max 3)
  actionsList.innerHTML = "";

  recs.forEach((r) => {
    const li = document.createElement("li");
    li.innerText = firstSentence(r.recommendation);
    actionsList.appendChild(li);
  });
}

// ✅ Render learning insights (max 2)
function renderLearning(l) {
  const learningList = document.getElementById("learning-list");
  learningList.innerHTML = "";

  const insights = Array.isArray(l.insights) ? l.insights.slice(0, 2) : [];

  insights.forEach((i) => {
    const li = document.createElement("li");
    li.innerText = firstSentence(i.detail);
    learningList.appendChild(li);
  });
}