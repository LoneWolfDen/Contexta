//const BASE_URL = "http://localhost:5000";
const BASE_URL = "https://animated-spoon-xrw755gpvpj429xpv-5000.app.github.dev";


// ✅ Load latest proposal
async function loadLatestProposal() {
  const res = await fetch(`${BASE_URL}/proposal`, {
      method: "GET"
    });
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



function simplifyCategory(cat) {
  if (cat.includes("missing_information")) return "Missing key inputs";
  if (cat.includes("missing_security")) return "Security gaps";
  return "Other risk";
}



// ✅ Render proposal (clean)
function renderProposal(p) {

  // Executive summary → shorten
  document.getElementById("proposal-content").innerHTML = `
    <strong>Summary:</strong>
    <p>${p.summary.executive_summary.split(".")[0]}</p>
  `;

  // ✅ Risks (top 3 only)
  const risks = document.getElementById("risks-list");
  risks.innerHTML = "";

  p.recommendations.slice(0, 3).forEach(r => {
    let li = document.createElement("li");
    li.innerText = simplifyCategory(r.category) + " (High risk)";
    risks.appendChild(li);
  });


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


// ✅ Render learning (short + readable)
function renderLearning(l) {
  const learningList = document.getElementById("learning-list");
  learningList.innerHTML = "";

  l.insights.slice(0, 2).forEach(i => {
    let li = document.createElement("li");

    // shorten insight
    let text = i.detail.split(".")[0];
    li.innerText = text;

    learningList.appendChild(li);
  });
}
