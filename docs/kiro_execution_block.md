# Kiro Execution Rules

Read BEFORE any change:
- docs/system_rules.md
- docs/architecture.md
- docs/data_model.md
- docs/api_contracts.md
- docs/sprint_plan.md

---

## Boundaries
- Modify ONLY listed files
- Do NOT refactor unrelated modules
- Do NOT rename models / fields / APIs
- If other files require change → list but DO NOT implement

---

## Coding Standards
- Use simple, readable functions
- Follow input → process → output pattern
- Avoid deeply nested logic
- Use consistent naming for IDs:
  project_id, version_id, review_id, etc.
- Keep modules independent (no cross-import loops)

---

## API Design Rule
- Always support extensible payloads:

example:
{
  "config": {
      "future_param": "allowed"
  }
}

---

## Testing Rule (MANDATORY)
- Add or update test cases for every new API or module
- Do NOT remove existing tests
- Tests must cover:
  - happy path
  - invalid input
  - traceability validation

- Test folder structure:
  tests/test_<module>.py

---

## Regression Safety
- After change:
  - existing APIs must still work
  - previous flow should NOT break

---

## Storage Rule
- SQLite → metadata
- Filesystem → JSON + XML + drawio

---

## Traceability Rule
Always maintain:

Project → Version → Review → Iteration → Reconciliation → Proposal

---

## Definition of Done
- Code runs locally
- No regression
- Data stored correctly
- Traceability maintained
- Tests updated and passing
