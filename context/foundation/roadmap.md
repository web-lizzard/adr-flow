---
project: adr-flow
version: 1
status: draft
created: 2026-06-08
updated: 2026-07-05
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

**S-05: User can edit a reviewed ADR without re-review and publish it as `proposed`** — delivered 2026-06-18; this was the validation milestone, the smallest end-to-end slice whose successful delivery proved the core product hypothesis (full one-session flow `draft → in_review → after_review → proposed`).

**Post-core iteration focus: `adr-validation-re-shape` (R-01)** — delivered; static gap detection, parallel per-section 0–5 ratings, and cross-section annotations. Validation failures complete to `after_review` (error-status); infrastructure failures use `review_failed` + retry.

## At a glance

| ID | Change ID | Outcome (user can …) | Prerequisites | PRD refs | Status |
|---|---|---|---|---|---|
| F-02 | persistence-scaffold | (foundation) Postgres driver, migration tooling, and initial schema contract for users and ADRs are in place | — | NFR: Per-user data isolation, NFR: Data retention, NFR: No draft loss, Access Control | done |
| F-01 | review-quality-checks | (foundation) review output can be checked against required-section and actionability guardrails | — | NFR: Static section gap detection, NFR: Annotation actionability | done |
| S-01 | account-access | register, log in, and reach a protected per-user ADR workspace | F-02 | US-03, FR-001, FR-003, Access Control, NFR: Per-user data isolation | done |
| S-02 | draft-authoring-persistence | create an ADR from the starter template, edit markdown, and recover saved draft content | S-01 | US-01, FR-004, FR-005, FR-006, NFR: No draft loss | done |
| S-04 | first-ai-review-annotations | submit a draft for AI review and see actionable annotations in `after_review` | S-02, F-01 | US-01, FR-007, FR-008, FR-010, FR-011, FR-012 | done |
| S-05 | publish-after-review | edit the reviewed ADR without re-review and publish it as `proposed` | S-04 | US-01, US-04, FR-005, FR-007, FR-009 | done |
| S-03 | adr-history-cards | return later, browse owned ADR cards, and reopen an existing ADR | S-02 | US-02, FR-013, NFR: Data retention | done |
| S-06 | remove-adr-from-active-list | remove an ADR from the active card view without permanently destroying it | S-03 | FR-015, NFR: Data retention | done |
| S-07 | review-validation-logs-only | always receive LLM review annotations in `after_review`; failed quality checks are logged only and never block the transition | S-04 | FR-008, FR-010, FR-011, FR-012, NFR: Annotation actionability | done |
| R-01 | adr-validation-re-shape | receive static gap detection, per-section 0–5 ratings, and strict validation on AI review output | S-04 | FR-008, FR-010, FR-011, FR-012, NFR: Static section gap detection, NFR: Annotation actionability | done |
| S-08 | jwt-bearer-access-token | authenticate with a JWT `access_token` in the `Authorization` header (no refresh token) instead of an httponly session cookie | S-01 | US-03, FR-003, Access Control | ready |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme | Chain | Note |
|---|---|---|---|
| A | Persistence & core loop | `F-02` → `S-01` → `S-02` → `S-04` → `S-05` | Core loop delivered; north star S-05 done. |
| B | Review-quality foundation | `F-01` → `R-01` | F-01 shipped harness; R-01 delivered static gaps + per-section ratings; error-status softened validation to logs-only. |
| C | History & lifecycle | `S-03` → `S-06` | Joins Stream A at `S-02`. |
| D | Auth transport | `S-08` | Parallel with Stream B; cookie → Bearer `access_token`, no refresh. |

## Baseline

What's already in place in the codebase as of `2026-06-19` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** present — Nuxt 4 with auth pages, workspace, ADR editor, history cards, review/publish flows (`frontend/app/`).
- **Backend / API:** present — FastAPI with auth, ADR CRUD, review submission, event-sourced lifecycle (`backend/infrastructure/api/`, `backend/application/`).
- **Data:** present — SQLAlchemy + Alembic, `users`/`adrs`/`events` tables, projections (`backend/infrastructure/adapters/persistence/`).
- **Auth:** present (cookie transport) — custom email/password, Argon2 hashing, HS256 JWT issued on login/register but stored in httponly `session` cookie (`backend/infrastructure/api/routers/auth.py`, `dependencies.py:88`). No Bearer header flow yet; no refresh token.
- **Deploy / infra:** present — `frontend/Dockerfile`, `deploy/gcp/`, `.github/workflows/deploy-gcp.yml` (Cloud Run, WIF).
- **Observability:** partial — structured application logging (`application/logging`); no metrics, error tracking, or OpenTelemetry.

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
- **Risk:** Delivered; vertical slices integrated persistence through real user behavior.
- **Status:** done

### F-01: Review Quality Checks

- **Outcome:** (foundation) review output can be checked against the required-section and actionability guardrails before the first review loop is treated as useful — a minimal verification harness, not a full review engine.
- **Change ID:** review-quality-checks
- **PRD refs:** NFR: Static section gap detection, NFR: Annotation actionability
- **Unlocks:** S-04, S-05, and the verification path for the PRD guardrails on AI annotations (deterministic static gaps; every issue carries a concrete corrective action)
- **Prerequisites:** —
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Delivered with harness grading static gap presence and actionability; R-01 reshapes runtime to match.
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
- **Risk:** Delivered with cookie-based JWT; S-08 migrates transport to Bearer `access_token` without changing registration/login semantics.
- **Status:** done

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
- **Risk:** Delivered; strict validation in R-01 replaces the original blocking-then-logs-only S-07 path.
- **Status:** done

### S-05: Publish After Review

- **Outcome:** user can edit the reviewed ADR without re-triggering review and publish it as `proposed`.
- **Change ID:** publish-after-review
- **PRD refs:** US-01, US-04, FR-005, FR-007, FR-009
- **Prerequisites:** S-04
- **Parallel with:** S-03, S-06
- **Blockers:** —
- **Unknowns:** —
- **Risk:** North star delivered; edits in `after_review` do not trigger re-review; user publishes when ready.
- **Status:** done

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
- **Parallel with:** S-05, S-07, S-08
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Removal only has user value once an active card list exists, so it is sequenced before post-core hardening slices.
- **Status:** done

### S-07: Review Validation Logs Only

- **Outcome:** user always receives LLM review annotations in `after_review`; when quality checks fail, the failure is logged for measurement but the ADR still transitions out of `in_review`.
- **Change ID:** review-validation-logs-only
- **PRD refs:** FR-008, FR-010, FR-011, FR-012, NFR: Annotation actionability
- **Prerequisites:** S-04
- **Parallel with:** S-06, S-08
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Superseded by R-01 (`adr-validation-re-shape`), which implements strict validation with static gap detection and per-section ratings instead of logs-only gating.
- **Status:** done

### R-01: ADR Validation Reshape

- **Outcome:** user receives deterministic static gap detection (score-0 ratings + `missing_section` annotations), per-section quality ratings (0–5) for all sections, and cross-section inconsistency/conciseness annotations; validation warnings are logged only and reviews complete to `after_review` (error-status).
- **Change ID:** adr-validation-re-shape
- **PRD refs:** FR-008, FR-010, FR-011, FR-012, NFR: Static section gap detection, NFR: Annotation actionability
- **Prerequisites:** S-04
- **Parallel with:** S-06, S-08
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Six parallel LLM calls per review replace one monolithic call; acceptable for MVP event-driven review with frontend polling.
- **Status:** done

### S-08: JWT Bearer Access Token

- **Outcome:** user can authenticate API calls with a JWT `access_token` in the `Authorization: Bearer` header; login/register return the token in the response body; no refresh token and no httponly session cookie.
- **Change ID:** jwt-bearer-access-token
- **PRD refs:** US-03, FR-003, Access Control
- **Prerequisites:** S-01
- **Parallel with:** S-06, S-07
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Transport change only — registration, login, and per-user isolation semantics stay the same. Frontend must store and attach the token; session expiry behavior follows JWT `exp` with no silent refresh in MVP.
- **Status:** ready

## Backlog Handoff

| Roadmap ID | Change ID | Suggested issue title | Ready for `/plan` | Notes |
|---|---|---|---|---|
| F-02 | persistence-scaffold | Add Postgres driver, migrations, and initial User/ADR schema | no | Done. |
| F-01 | review-quality-checks | Add review-quality checks for required-section and actionability guardrails | no | Done; R-01 reshapes runtime validation. |
| S-01 | account-access | Let users register, log in, and reach a protected ADR workspace | no | Done; S-08 migrates token transport. |
| S-02 | draft-authoring-persistence | Let users create and safely save ADR drafts from the starter template | no | Done. |
| S-04 | first-ai-review-annotations | Let users submit a draft and receive actionable AI review annotations | no | Done. |
| S-05 | publish-after-review | Let users edit reviewed ADRs and publish them as proposed | no | Done (north star). |
| S-03 | adr-history-cards | Let users browse ADR history cards and reopen existing ADRs | no | Done. |
| S-06 | remove-adr-from-active-list | Let users remove ADRs from the active card view | yes | Run `/plan remove-adr-from-active-list`. |
| S-07 | review-validation-logs-only | Return every LLM review to after_review; log validation failures only | no | Superseded by R-01 (`adr-validation-re-shape`). |
| R-01 | adr-validation-re-shape | Static gaps, per-section ratings, review validation | no | Done; error-status softened validation gate. |
| S-08 | jwt-bearer-access-token | Switch auth from session cookie to Bearer access_token (no refresh) | yes | Run `/plan jwt-bearer-access-token`; can parallel S-06. |

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
- **Conditional re-review (S-09).** — Why parked: With static gaps and per-section ratings, almost every ADR already has actionable feedback in `after_review`; error-status ensures reviews always land there. The user edits and publishes when ready — a second AI pass duplicates the pipeline without a clear eligibility rule (`len(annotations) > 0` matches nearly all ADRs). Roadmap slice cancelled 2026-07-05 → `context/archive/2026-06-19-conditional-adr-re-review/`.
- **Unlimited or quota-based re-review.** — Why parked: Broader re-review variants remain post-MVP if product need emerges.
- **Configurable ADR conventions.** — Why parked: PRD Functional Non-Goals; the MVP hard-codes five required sections.
- **Filtering or search in the ADR list.** — Why parked: PRD Functional Non-Goals; card view is sufficient for small personal history.
- **Accepted and superseded statuses.** — Why parked: PRD Functional Non-Goals; MVP stops at `proposed`.
- **Password reset.** — Why parked: PRD Functional Non-Goals; manual recovery remains an open post-MVP risk.
- **Permanent ADR destruction.** — Why parked: PRD Functional Non-Goals; MVP removal hides the ADR from active view only.
- **Shared workspaces or team features.** — Why parked: PRD Functional Non-Goals; one user equals one isolated space in MVP.
- **ADR export (markdown / PDF).** — Why parked: PRD Functional Non-Goals; ADRs remain inside the product for MVP.
- **Visible progress or hard SLA for AI review duration.** — Why parked: PRD Non-functional Non-Goals; accepted MVP UX risk unless pilots prove otherwise.
- **JWT refresh tokens.** — Why parked: explicit out of scope for S-08; users re-login when `access_token` expires.

## Done

- **S-06: user can remove an ADR from the active card view while the record remains retained (soft-delete).** — Archived 2026-07-05 → `context/archive/2026-07-05-remove-adr-from-active-list/`. Lesson: —.
- **S-09: user can request one additional AI review when the first review reported errors (non-empty actionable annotations) — at most once per ADR; edits in `after_review` still do not auto-trigger review.** — Cancelled 2026-07-05 → `context/archive/2026-06-19-conditional-adr-re-review/`. Lesson: ratings + user-driven `after_review` make conditional re-review redundant; eligibility predicate never resolved.
- **S-07: user always receives LLM review annotations in `after_review`; when quality checks fail, the failure is logged for measurement but the ADR still transitions out of `in_review`.** — Archived 2026-07-05 → `context/archive/2026-06-19-review-validation-logs-only/`. Lesson: superseded by R-01; never implemented.
- **S-01: user can register, log in, and reach a protected per-user ADR workspace.** — Archived 2026-07-05 → `context/archive/2026-06-14-account-access/`. Lesson: —.
- **S-02: user can create an ADR from the starter template, edit markdown, and recover saved draft content after leaving or refreshing.** — Archived 2026-06-16 → `context/archive/2026-06-16-draft-authoring-persistence/`. Lesson: —.
- **S-03: user can return later, browse owned ADR cards (title, status, last-edited), and reopen an existing ADR where editing is allowed.** — Archived 2026-06-16 → `context/archive/2026-06-16-adr-history-cards/`. Lesson: —.
- **F-01: (foundation) review output can be checked against the required-section and actionability guardrails before the first review loop is treated as useful — a minimal verification harness, not a full review engine.** — Archived 2026-06-16 → `context/archive/2026-06-16-review-quality-checks/`. Lesson: —.
- **S-04: user can submit a draft for AI review and see actionable missing-section, inconsistency, and conciseness annotations in `after_review`.** — Archived 2026-06-18 → `context/archive/2026-06-17-first-ai-review-annotations/`. Lesson: —.
- **S-05: user can edit the reviewed ADR without re-triggering review and publish it as `proposed`.** — Archived 2026-06-18 → `context/archive/2026-06-18-publish-after-review/`. Lesson: —.
- **F-02: (foundation) Postgres driver, migration tooling, and initial schema contract for `User` and `ADR` entities are in place — including per-user ownership (`user_id`), the four-status lifecycle field, markdown content storage, timestamps, and a soft-delete flag for FR-015.** — Archived 2026-06-19 → `context/archive/2026-06-14-persistence-scaffold/`. Lesson: —.
- **R-01: user receives deterministic static gap detection (score-0 ratings + `missing_section` annotations), per-section quality ratings (0–5) for all sections, and cross-section inconsistency/conciseness annotations; validation warnings are logged only and reviews complete to `after_review`.** — Archived 2026-07-04 → `context/archive/2026-06-26-adr-validation-re-shape/`. Lesson: strict-validation outcome superseded by error-status.
