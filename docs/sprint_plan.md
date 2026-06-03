# Contexta V3 - Sprint Plan and Kiro Pack

## Product Name
**Contexta**

Short description:
A traceable, learning-driven decision intelligence platform.

---

# Sprint Plan

## Sprint 0 - Foundation and Core Engine
**Goal**
Create the minimal working platform backbone with modular APIs, local storage, and locked traceability path:
Project -> Ingest -> Version -> Review.

**Scope**
- Project module
- Artifact ingestion module
- Version module
- Basic review module
- SQLite metadata storage
- File storage structure
- Health endpoint
- Docker baseline

**Acceptance Criteria**
- User can create a project.
- User can upload one or more artifacts to a project.
- Uploaded artifacts are stored locally and metadata is saved in SQLite.
- User can mark artifacts as included or excluded for downstream use.
- User can create a version using selected included artifacts.
- System creates a unique `version_id` and stores a version snapshot.
- User can run a basic review against a selected version.
- System creates a unique `review_id` linked to `version_id`.
- Basic traceability exists from project to version to review.
- Application starts locally through Docker.
- Health endpoint returns success.

---

## Sprint 1 - Version Intelligence Summary
**Goal**
Generate a structured summary of what the system understood from included artifacts when a version is built.

**Scope**
- Version summary generator
- Structured summary sections
- Confidence and missing information indicators
- Store summary as JSON linked to version

**Acceptance Criteria**
- When a version is created, the system generates a `version_summary`.
- Version summary contains these sections when relevant:
  - Client ask
  - Solution understanding
  - Technology landscape
  - Delivery model
  - Tooling recommendations from client artifacts
  - Constraints including geography, timezone, SLA, KPI, dependencies
  - Architecture understanding
- System highlights missing information where the source data is weak.
- Version summary is stored and can be reused by later modules.
- Version summary is visible in UI in a simple collapsed format.

---

## Sprint 2 - Review Engine
**Goal**
Create the main review engine using version context, personas, base prompts, and optional SME question generation.

**Scope**
- Persona selection
- Prompt builder
- Ask SME section
- Weakness extraction
- Review history list

**Acceptance Criteria**
- User can select up to configured number of personas.
- User can run a review against a selected version.
- System stores review metadata including personas and provider used.
- System generates weaknesses linked to the review.
- Each weakness contains category, severity, description, and optional user notes.
- User can view review history grouped under version.
- Version summary is used as review context.
- Review output is stored as reusable structured JSON.

---

## Sprint 3 - Iteration
**Goal**
Allow review refinement without overwriting the original review.

**Scope**
- Iteration workflow
- Review-on-review chaining
- Iteration prompts
- Output review linking

**Acceptance Criteria**
- User can select an existing review and create an iteration from it.
- Original review remains unchanged.
- System creates a new review linked to the base review.
- User can see whether a review is independent or chained.
- Iteration output remains traceable to both version and prior review.

---

## Sprint 4 - Reconciliation
**Goal**
Allow users to compare and merge multiple reviews into one reconciled output.

**Scope**
- Multi-review selection
- Anchor review selection
- Reconciliation modes
- Reconciliation output storage

**Acceptance Criteria**
- User can select multiple reviews for reconciliation.
- User can set an anchor review.
- System supports at least:
  - compare
  - merge
  - consensus
- Reconciliation result is stored with a unique `recon_id`.
- Reconciliation output is traceable to all source reviews.
- System blocks invalid reconciliation input when no reviews are selected.

---

## Sprint 5 - Proposal Engine
**Goal**
Generate one or more proposal outputs from review or reconciliation context, with optional diagrams, references, and KPI suggestions.

**Scope**
- Proposal generation
- Optional final user prompt
- Artifact references
- KPI suggestions section
- Diagram output in draw.io XML
- Export formats

**Acceptance Criteria**
- User can generate multiple proposals from one reconciliation or selected review set.
- User can optionally add a final guidance prompt before proposal generation.
- Proposal includes artifact references where available.
- Proposal can include suggested KPI section as optional reference content.
- Proposal can include a simple architecture or component diagram.
- Proposal outputs are stored as JSON.
- Proposal export supports JSON and XML.
- Draw.io XML is generated for diagrammatic output where relevant.

---

## Sprint 6 - Learning Layer
**Goal**
Reuse generated intelligence across projects, versions, reviews, and proposals to improve future outputs in a controlled way.

**Scope**
- Client memory
- Prompt suggestion engine
- Suggested recommendations store
- Admin review and approval flow

**Acceptance Criteria**
- System stores reusable intelligence patterns from prior outputs.
- System can generate suggested prompt improvements from available project intelligence.
- Suggested prompt updates are never auto-applied.
- Admin can review and approve or reject prompt updates.
- Client-specific recommendation snippets can be suggested in Ask SME and Proposal areas.
- Learning outputs are stored separately from approved base prompts.

---

## Sprint 7 - Admin and Settings
**Goal**
Make all major operating parameters centrally configurable.

**Scope**
- Settings tab
- Admin tab
- Prompt library
- Persona management
- AI provider config
- System limits

**Acceptance Criteria**
- Admin can configure:
  - max projects
  - max versions per project
  - max reviews per version
  - available AI providers
  - provider endpoints and keys
  - base personas
  - base prompts
  - feature flags
- Application loads settings from a single config source.
- All modules read limits and settings from config rather than hardcoded values.
- Settings changes apply without code changes.

---

## Sprint 8 - UX and Packaging
**Goal**
Make the product simple, lightweight, and usable by non-technical users.

**Scope**
- Simple mode and advanced mode
- collapsible panels
- traceability panel
- guided journey
- polished Docker packaging

**Acceptance Criteria**
- UI supports a simple mode for non-technical users.
- UI supports an advanced mode for deeper controls.
- Long pages use collapsible sections.
- Traceability path is visible across major screens.
- Guided step flow is available:
  1. Add artifacts
  2. Build version
  3. Run review
  4. Refine
  5. Reconcile
  6. Generate proposal
- Non-technical user can run the app locally with Docker and their own API keys.

---

# Single Kiro Block - Token Optimized
Save this under `docs/kiro_execution_block.md`

```md
# Kiro Execution Block

Read these files before making any change:
- docs/system_rules.md
- docs/architecture.md
- docs/data_model.md
- docs/api_contracts.md
- docs/sprint_plan.md

Mandatory rules:
- Modify only the files named in the task.
- Do not refactor unrelated modules.
- Do not rename fields, models, APIs, or folders unless explicitly asked.
- If another file also needs change, list it under "Required follow-up" but do not implement it.
- Keep modules independent. Each module must behave as input -> process -> output.
- Preserve traceability:
  Project -> Version -> Review -> Iteration -> Reconciliation -> Proposal
- Use config-driven values for limits, personas, prompts, and AI providers.
- Keep UI simple, lightweight, and collapsible.
- Store metadata in SQLite and files/outputs in filesystem JSON or draw.io XML.

Task format you must follow:
1. Objective
2. Files allowed to modify
3. Inputs
4. Processing logic
5. Outputs
6. Acceptance criteria
7. Required follow-up

Definition of done:
- Code runs locally.
- Existing working flow is not broken.
- New output is stored with traceability.
- Acceptance criteria are met exactly.
```
---

# Suggested Repo Files To Create Now
Create these files in the repo so Kiro can read them instead of relying on chat context:

- `docs/system_rules.md`
- `docs/architecture.md`
- `docs/data_model.md`
- `docs/api_contracts.md`
- `docs/sprint_plan.md`
- `docs/kiro_execution_block.md`

Recommended action:
- Save the sprint plan section of this file as `docs/sprint_plan.md`
- Save the Kiro block section as `docs/kiro_execution_block.md`

---

# Local Viewing Notes
- `.drawio` files can be opened locally in diagrams.net desktop or in the browser at app.diagrams.net.
- Markdown `.md` files can be opened in VS Code, GitHub, or any text editor.
- JSON and XML outputs can be viewed in VS Code without extra tools.
