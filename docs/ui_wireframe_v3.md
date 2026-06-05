# Contexta UI-lite V3 Wireframe

## Goal
Create a simple, low-noise dashboard for non-technical users.

## UX principles
- Show only top 3 items per section by default
- Use plain English labels
- Hide secondary details behind expand/collapse
- Avoid deep tree structures
- Avoid long paragraphs
- Use cards with strong spacing
- Keep layout light and readable

## Page 1: Dashboard

### Header
- Product name: Contexta
- Small project selector
- Small version selector
- Button: Refresh

### Section A: Overview
Card title: Overview
Show:
- Project name
- Selected version
- Review status
- Proposal status

### Section B: Top Risks
Card title: Key Risks
Show max 3 items:
- Missing key inputs
- Security gaps
- Delivery uncertainty

Each item should show:
- simple label
- priority badge (High / Medium / Low)

Button:
- View All Risks

### Section C: Next Actions
Card title: Next Actions
Show max 3 items:
- Define missing inputs
- Run security review
- Confirm delivery model

Button:
- View Full Proposal

### Section D: Proposal Summary
Card title: Proposal Summary
Show:
- one short executive summary sentence
- one short recommended solution sentence

Button:
- Open Proposal

### Section E: Key Learnings
Card title: Key Learnings
Show max 2 items only

Button:
- View Learning Log

## Page 2: Review Detail
- Summary
- Top weaknesses
- Explainability
- Personas used
- Prompt context (collapsed by default)

## Page 3: Reconciliation
- Consensus findings
- Merged risks
- Conflicts
- Recommended focus

## Page 4: Proposal
- Executive summary
- Recommended solution
- Recommendations
- Delivery considerations
- KPIs
- References

## Page 5: Learning
- Insights
- Prompt suggestions
- Reusable patterns
- Approval status

## Interaction rules
- All detail sections collapsed by default
- All API errors should show friendly message
- Do not expose raw backend field names like:
  - missing_information
  - prompt_context
  - merged_weaknesses
- Replace with user-friendly labels
