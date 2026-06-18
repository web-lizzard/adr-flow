---
project: adr-flow
version: 1
status: draft
created: 2026-06-08
updated: 2026-06-18
prd_version: 1
main_goal: speed
top_blocker: time
---

# Roadmap: adr-flow

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Vision recap

ADR Flow helps an individual tech lead or architect turn a first ADR draft into a shorter, more complete document before a human reviewer spends time on formal gaps. The product promise is a hosted loop: start from a fixed markdown template, publish for AI review, fix the annotated issues, and publish the ADR as `proposed`. The product *wedge* — the one trait that, if removed, makes this indistinguishable from a generic markdown editor — is AI review that reliably flags missing required sections and over-long passages with concrete, actionable fixes.

## North star

**S-05: User can edit a reviewed ADR without re-review and publish it as `proposed`** — this is the validation milestone, the smallest end-to-end slice whose successful delivery proves the core product hypothesis. It completes Success Criterion #1's full one-session flow (`draft → in_review → after_review → proposed`); if this loop does not work end to end, nothing else in the product matters. Under the `speed` goal it is placed as early as its prerequisites (the authoring + review path) allow.

## At a glance

| ID | Change ID | Outcome (user can …) | Prerequisites | PRD refs | Status |
|---|---|---|---|---|---|
| F-02 | persistence-scaffold | (foundation) Postgres driver, migration tooling, and initial schema contract for users and ADRs are in place | — | NFR: Per-user data isolation, NFR: Data retention, NFR: No draft loss, Access Control | ready |
| F-01 | review-quality-checks | (foundation) review output can be checked against required-section and actionability guardrails | — | NFR: Section gap detection accuracy, NFR: Annotation actionability | done |
| S-01 | account-access | register, log in, and reach a protected per-user ADR workspace | F-02 | US-03, FR-001, FR-003, Access Control, NFR: Per-user data isolation | proposed |
| S-02 | draft-authoring-persistence | create an ADR from the starter template, edit markdown, and recover saved draft content | S-01 | US-01, FR-004, FR-005, FR-006, NFR: No draft loss | done |
| S-04 | first-ai-review-annotations | submit a draft for AI review and see actionable annotations in `after_review` | S-02, F-01 | US-01, FR-007, FR-008, FR-010, FR-011, FR-012 | done |
| S-05 | publish-after-review | edit the reviewed ADR without re-review and publish it as `proposed` | S-04 | US-01, US-04, FR-005, FR-007, FR-009 | proposed |
| S-03 | adr-history-cards | return later, browse owned ADR cards, and reopen an existing ADR | S-02 | US-02, FR-013, NFR: Data retention | done |
| S-06 | remove-adr-from-active-list | remove an ADR from the active card view without permanently destroying it | S-03 | FR-015, NFR: Data retention | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme | Chain | Note |
|---|---|---|---|
| A | Persistence & core loop | `F-02` → `S-01` → `S-02` → `S-04` → `S-05` | `F-02` gates every DB-dependent slice; this is the must-have path to the north star. |
| B | Review-quality foundation | `F-01` | Parallel with `F-02`; joins Stream A at `S-04`. |
| C | History & lifecycle | `S-03` → `S-06` | Joins Stream A at `S-02`; sequenced after the core loop under `speed`. |

## Baseline

What's already in place in the codebase as of `2026-06-08` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** present (scaffold) — Nuxt 4 app with health demo only; no feature pages yet (`frontend/app/pages/index.vue`, `frontend/nuxt.config.ts`).
- **Backend / API:** present (scaffold) — FastAPI app exposing only `GET /health`; no feature routers (`backend/main.py`).
- **Data:** partial — Postgres wired in devcontainer and GCP deploy (`.devcontainer/docker-compose.yml`, `deploy/gcp/03-gce-postgres.sh`), but NO DB driver/ORM, models, or migrations in the backend.
- **Auth:** absent — no auth dependencies, no login/register/token code, no route guards; custom JWT is docs-only (`tech-stack.md`).
- **Deploy / infra:** present — `frontend/Dockerfile`, `deploy/gcp/` (17 files), `.github/workflows/deploy-gcp.yml` (Cloud Run, WIF).
- **Observability:** absent — no app logging, metrics, error tracking, or OpenTelemetry instrumentation in source.

## Foundations

### F-02: Persistence Scaffold

- **Outcome:** (foundation) Postgres driver, migration tooling, and initial schema contract for `User` and `ADR` entities are in place — including per-user ownership (`user_id`), the four-status lifecycle field, markdown content storage, timestamps, and a soft-delete flag for FR-015.
- **Change ID:** persistence-scaffold
- **PRD refs:** NFR: Per-user data isolation, NFR: Data retention, NFR: No draft loss, Access Control
- **Unlocks:** S-01, S-02, S-03, S-06 — every slice that reads or writes application state
- **Prerequisites:** —
- **Parallel with:** F-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Sequenced first because the baseline reports Data as `partial` — infra exists but no application persistence. Without tables and migrations, no other stream can store users or ADRs. Scope is the minimal schema contract, not a complete data layer; vertical slices still integrate persistence through real user behavior.
- **Status:** ready

### F-01: Review Quality Checks

- **Outcome:** (foundation) review output can be checked against the required-section and actionability guardrails before the first review loop is treated as useful — a minimal verification harness, not a full review engine.
- **Change ID:** review-quality-checks
- **PRD refs:** NFR: Section gap detection accuracy, NFR: Annotation actionability
- **Unlocks:** S-04, S-05, and the verification path for the PRD guardrails on AI annotations (≥80% section-gap detection; every issue carries a concrete corrective action)
- **Prerequisites:** —
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Sequenced before the AI-review slice so the product does not mistake any annotation output for *useful* annotation output. This is the wedge; under `speed` it gets invested in just enough to clear the guardrail, then S-04 integrates it through real user behavior. Independent of persistence — can run alongside F-02.
- **Status:** done

## Slices

### S-01: Account Access

- **Outcome:** user can register, log in, and reach a protected per-user ADR workspace.
- **Change ID:** account-access
- **PRD refs:** US-03, FR-001, FR-003, Access Control, NFR: Per-user data isolation
- **Prerequisites:** F-02
- **Parallel with:** F-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Every ADR capability is per-user; weak access boundaries would undermine all later slices. Auth and API isolation build on the `User` entity from F-02 — this slice wires registration, login, JWT, and route guards, not the schema itself.
- **Status:** proposed

### S-02: Draft Authoring & Persistence

- **Outcome:** user can create an ADR from the starter template, edit markdown, and recover saved draft content after leaving or refreshing.
- **Change ID:** draft-authoring-persistence
- **PRD refs:** US-01, FR-004, FR-005, FR-006, NFR: No draft loss
- **Prerequisites:** S-01
- **Parallel with:** F-01
- **Blockers:** —
- **Unknowns:**
  - Does save-on-blur plus save-on-unload actually suffice against draft loss? — Owner: user. Block: no.
- **Risk:** This slice introduces the first real ADR state on top of the F-02 schema; if persistence is unreliable, the later review loop will hide the most important failure. Kept simple under `speed` — save-on-blur + save-on-unload, no continuous autosave.
- **Status:** done

### S-04: First AI Review Annotations

- **Outcome:** user can submit a draft for AI review and see actionable missing-section, inconsistency, and conciseness annotations in `after_review`.
- **Change ID:** first-ai-review-annotations
- **PRD refs:** US-01, FR-007, FR-008, FR-010, FR-011, FR-012
- **Prerequisites:** S-02, F-01
- **Parallel with:** S-03
- **Blockers:** —
- **Unknowns:**
  - Will "no visible progress" for AI review cause mass tab closures during the review wait? — Owner: user. Block: no.
- **Risk:** This is the highest-value capability and the wedge made real; it is sequenced as soon as drafts and the quality checks exist so the core loop reaches the north star fast.
- **Status:** done

### S-05: Publish After Review

- **Outcome:** user can edit the reviewed ADR without re-triggering review and publish it as `proposed`.
- **Change ID:** publish-after-review
- **PRD refs:** US-01, US-04, FR-005, FR-007, FR-009
- **Prerequisites:** S-04
- **Parallel with:** S-03, S-06
- **Blockers:** —
- **Unknowns:** —
- **Risk:** This is the north star; it completes the first proof point. Without it, review feedback never turns into a publishable ADR and Success Criterion #1 stays unmet.
- **Status:** proposed

### S-03: ADR History Cards

- **Outcome:** user can return later, browse owned ADR cards (title, status, last-edited), and reopen an existing ADR where editing is allowed.
- **Change ID:** adr-history-cards
- **PRD refs:** US-02, FR-013, NFR: Data retention
- **Prerequisites:** S-02
- **Parallel with:** S-04, S-05
- **Blockers:** —
- **Unknowns:** —
- **Risk:** History proves lasting value (the Secondary success criterion), but under `speed` it follows the core loop because empty history has nothing meaningful to show until drafts exist.
- **Status:** done

### S-06: Remove ADR From Active List

- **Outcome:** user can remove an ADR from the active card view while the record remains retained (soft-delete).
- **Change ID:** remove-adr-from-active-list
- **PRD refs:** FR-015, NFR: Data retention
- **Prerequisites:** S-03
- **Parallel with:** S-05
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Removal only has user value once an active card list exists, so it is sequenced last; the soft-delete flag from F-02 is exercised here through real user behavior.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID | Suggested issue title | Ready for `/plan` | Notes |
|---|---|---|---|---|
| F-02 | persistence-scaffold | Add Postgres driver, migrations, and initial User/ADR schema | yes | Run `/plan persistence-scaffold` first — gates all DB-dependent slices. |
| F-01 | review-quality-checks | Add review-quality checks for required-section and actionability guardrails | yes | Can run alongside F-02. |
| S-01 | account-access | Let users register, log in, and reach a protected ADR workspace | no | Requires F-02. |
| S-02 | draft-authoring-persistence | Let users create and safely save ADR drafts from the starter template | no | Requires S-01. |
| S-04 | first-ai-review-annotations | Let users submit a draft and receive actionable AI review annotations | no | Requires S-02 and F-01. |
| S-05 | publish-after-review | Let users edit reviewed ADRs and publish them as proposed | no | Requires S-04; completes the first proof point (north star). |
| S-03 | adr-history-cards | Let users browse ADR history cards and reopen existing ADRs | no | Requires S-02. |
| S-06 | remove-adr-from-active-list | Let users remove ADRs from the active card view | no | Requires S-03. |

## Open Roadmap Questions

1. **Does save-on-blur + save-on-unload actually suffice against draft loss?** — Owner: user. Block: none (FR-006 stands; gates S-02 only if QA finds an unload-trigger edge case).
2. **What happens to a user who forgot their password?** — Owner: user. Block: none; post-MVP account-retention risk (no password reset in MVP).
3. **Will "no visible progress" for AI review cause mass tab closures during review?** — Owner: user. Block: none; gates S-04 only if first-pilot evidence shows the wait state prevents completion.

## Parked

- **Email notification when AI review completes (FR-014).** — Why parked: PRD nice-to-have; promote only if the no-progress review wait becomes a real retention problem.
- **Automatic ADR generation from repository code.** — Why parked: PRD Functional Non-Goals; the MVP is for authoring ADRs, not generating them from code.
- **External code-hosting integrations.** — Why parked: PRD Functional Non-Goals; all context is supplied by the author in ADR content.
- **Real-time multi-user collaboration.** — Why parked: PRD Functional Non-Goals; B2C/PLG MVP is one author per ADR.
- **Advanced approval workflow.** — Why parked: PRD Functional Non-Goals; AI review replaces formal human approval in MVP.
- **Automatic committing of ADRs to a repository.** — Why parked: PRD Functional Non-Goals; ADRs live in the hosted product.
- **Re-review after ADR edits.** — Why parked: PRD Functional Non-Goals; review runs once in the ADR lifecycle.
- **Configurable ADR conventions.** — Why parked: PRD Functional Non-Goals; the MVP hard-codes five required sections.
- **Filtering or search in the ADR list.** — Why parked: PRD Functional Non-Goals; card view is sufficient for small personal history.
- **Accepted and superseded statuses.** — Why parked: PRD Functional Non-Goals; MVP stops at `proposed`.
- **Password reset.** — Why parked: PRD Functional Non-Goals; manual recovery remains an open post-MVP risk.
- **Permanent ADR destruction.** — Why parked: PRD Functional Non-Goals; MVP removal hides the ADR from active view only.
- **Shared workspaces or team features.** — Why parked: PRD Functional Non-Goals; one user equals one isolated space in MVP.
- **ADR export (markdown / PDF).** — Why parked: PRD Functional Non-Goals; ADRs remain inside the product for MVP.
- **Visible progress or hard SLA for AI review duration.** — Why parked: PRD Non-functional Non-Goals; accepted MVP UX risk unless pilots prove otherwise.

## Done

<!-- Empty on first generation. `/archive` appends entries here when matching changes are archived. -->

- **S-02: user can create an ADR from the starter template, edit markdown, and recover saved draft content after leaving or refreshing.** — Archived 2026-06-16 → `context/archive/2026-06-16-draft-authoring-persistence/`. Lesson: —.
- **S-03: user can return later, browse owned ADR cards (title, status, last-edited), and reopen an existing ADR where editing is allowed.** — Archived 2026-06-16 → `context/archive/2026-06-16-adr-history-cards/`. Lesson: —.
- **F-01: (foundation) review output can be checked against the required-section and actionability guardrails before the first review loop is treated as useful — a minimal verification harness, not a full review engine.** — Archived 2026-06-16 → `context/archive/2026-06-16-review-quality-checks/`. Lesson: —.
- **S-04: user can submit a draft for AI review and see actionable missing-section, inconsistency, and conciseness annotations in `after_review`.** — Archived 2026-06-18 → `context/archive/2026-06-17-first-ai-review-annotations/`. Lesson: —.
