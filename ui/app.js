const BASE_URL = "http://localhost:5000";

// ---------------------------------------------------------------------------
// Label mapping — replaces technical terms with user-friendly labels
// ---------------------------------------------------------------------------
const LABEL_MAP = {
  missing_information: "Missing key inputs",
  missing_security_context: "Security gaps",
};

function friendlyLabel(text) {
  if (!text) return text;
  let result = text;
  Object.entries(LABEL_MAP).forEach(([key, value]) => {
    result = result.split(key).join(value);
  });
  return result;
}

// ---------------------------------------------------------------------------
// Trim text to first sentence only
// ---------------------------------------------------------------------------
function firstSentence(text) {
  if (!text) return "";
  const match = text.match(/^[^.!?]*[.!?]/);
  return match ? match[0].trim() : text.trim();
}

// ---------------------------------------------------------------------------
// Status message helper
// ---------------------------------------------------------------------------
function showStatus(message, isError) {
  const el = document.getElementById("status-message");
  el.textContent = message;
  el.className = "status-message " + (isError ? "status-error" : "status-ok");
}

function clearStatus() {
  const el = document.getElementById("status-message");
  el.textContent = "";
  el.className = "status-message hidden";
}

// ---------------------------------------------------------------------------
// Load latest proposal
// ---------------------------------------------------------------------------
async function loadLatestProposal() {
  clearStatus();
  const btn = document.getElementById("btn-load-proposal");
  btn.disabled = true;
  btn.textContent = "Loading…";

  try {
    const res = await fetch(`${BASE_URL}/proposal`);
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      showStatus("No proposals found. Generate a proposal first.", true);
      return;
    }

    const proposal = data[data.length - 1];
    renderProposal(proposal);
    showStatus("Proposal loaded successfully.", false);
  } catch (err) {
    showStatus("Could not load proposal. Is the server running?", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Load Latest Proposal";
  }
}

// ---------------------------------------------------------------------------
// Load latest learning
// ---------------------------------------------------------------------------
async function loadLatestLearning() {
  clearStatus();
  const btn = document.getElementById("btn-load-learning");
  btn.disabled = true;
  btn.textContent = "Loading…";

  try {
    const res = await fetch(`${BASE_URL}/learning`);
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      showStatus("No learning records found. Generate learning from a proposal first.", true);
      return;
    }

    const latest = data[data.length - 1];
    renderLearning(latest);
    showStatus("Learning insights loaded.", false);
  } catch (err) {
    showStatus("Could not load learning insights. Is the server running?", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Load Learning Insights";
  }
}

// ---------------------------------------------------------------------------
// Render proposal — summary, top 3 risks, top 3 actions
// ---------------------------------------------------------------------------
function renderProposal(p) {
  // Summary
  const summary = (p.summary && p.summary.executive_summary)
    ? firstSentence(friendlyLabel(p.summary.executive_summary))
    : "No summary available.";

  document.getElementById("proposal-content").innerHTML =
    `<p class="summary-text">${summary}</p>`;

  // Risks — top 3, badge for priority, label mapping on category
  const risksList = document.getElementById("risks-list");
  risksList.innerHTML = "";

  const recommendations = Array.isArray(p.recommendations) ? p.recommendations : [];
  const top3Risks = recommendations.slice(0, 3);

  if (top3Risks.length === 0) {
    risksList.innerHTML = '<li class="empty-state">No risks identified.</li>';
  } else {
    top3Risks.forEach(r => {
      const li = document.createElement("li");
      li.className = "item-row";
      const label = friendlyLabel(r.category || "Unknown");
      const priority = r.priority || "low";
      li.innerHTML = `
        <span class="item-label">${label}</span>
        <span class="badge badge-${priority}">${priority}</span>
      `;
      risksList.appendChild(li);
    });
  }

  // Actions — top 3, first sentence only, label mapping
  const actionsList = document.getElementById("actions-list");
  actionsList.innerHTML = "";

  if (top3Risks.length === 0) {
    actionsList.innerHTML = '<li class="empty-state">No actions required.</li>';
  } else {
    top3Risks.forEach(r => {
      const li = document.createElement("li");
      li.className = "item-row";
      const text = firstSentence(friendlyLabel(r.recommendation || "No recommendation."));
      li.innerHTML = `<span class="item-text">${text}</span>`;
      actionsList.appendChild(li);
    });
  }
}

// ---------------------------------------------------------------------------
// Render learning — top 2 insights, first sentence only, label mapping
// ---------------------------------------------------------------------------
function renderLearning(l) {
  const learningList = document.getElementById("learning-list");
  learningList.innerHTML = "";

  const insights = Array.isArray(l.insights) ? l.insights : [];
  const top2 = insights.slice(0, 2);

  if (top2.length === 0) {
    learningList.innerHTML = '<li class="empty-state">No insights available.</li>';
    return;
  }

  top2.forEach(insight => {
    const li = document.createElement("li");
    li.className = "item-row";
    const text = firstSentence(friendlyLabel(insight.detail || ""));
    li.innerHTML = `<span class="item-text">${text}</span>`;
    learningList.appendChild(li);
  });
}
