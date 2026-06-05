//const BASE_URL = "http://localhost:5000";
const BASE_URL = "https://animated-spoon-xrw755gpvpj429xpv-5000.app.github.dev";


// ✅ Load latest proposal
async function loadLatestProposal() {
  const res = await fetch(`${BASE_URL}/proposal`);
  const data = await res.json();

  // assume latest = last item
  const proposal = data[data.length - 1];

  renderProposal(proposal);
}

// ✅ Load learning
async function loadLatestLearning() {
  const res = await fetch(`${BASE_URL}/learning`);
  const data = await res.json();

  const latest = data[data.length - 1];

  renderLearning(latest);
}

// ✅ Render proposal
function renderProposal(p) {

  document.getElementById("proposal-content").innerHTML = `
    <strong>Executive Summary:</strong>
    <p>${p.summary.executive_summary}</p>
  `;

  // Risks
  const risks = document.getElementById("risks-list");
  risks.innerHTML = "";

  p.recommendations.slice(0, 3).forEach(r => {
    let li = document.createElement("li");
    li.innerText = `${r.category} (${r.priority})`;
    risks.appendChild(li);
  });

  // Actions
  const actions = document.getElementById("actions-list");
  actions.innerHTML = "";

  p.recommendations.slice(0, 3).forEach(r => {
    let li = document.createElement("li");
    li.innerText = r.recommendation;
    actions.appendChild(li);
  });
}

// ✅ Render learning
function renderLearning(l) {

  const learningList = document.getElementById("learning-list");
  learningList.innerHTML = "";

  l.insights.slice(0, 3).forEach(i => {
    let li = document.createElement("li");
    li.innerText = i.detail;
    learningList.appendChild(li);
  });
}
