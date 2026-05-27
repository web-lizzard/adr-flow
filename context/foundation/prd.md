---
project: adr-flow
version: 1
status: draft
created: 2026-05-19
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 3
  hard_deadline: null
  after_hours_only: true
---

## Vision & Problem Statement

A tech lead or architect on a product team writing an ADR — when drafting for the first time, during PR review, or while onboarding new people — faces inconsistent documents that are too verbose or too short and omit key sections (context, alternatives, decision, consequences). The cost today falls on others: the author pulls collaborating architects into many rounds of **formal** review (missing sections, overly granular content), stretching decisions by days or weeks and wasting their time on non-substantive issues.

Existing ADR tooling focuses on storage and scaffolding, not document quality assessment. The "template → AI review → fix" loop as a ready-made product does not exist — everyone assumes a human reviewer enforces ADR quality. At the same time, AI review capabilities are now good enough to evaluate structured docs like ADRs, and the ADR-as-product market is perceived as too narrow for anyone to assemble into one product — which leaves an open niche for individual tech leads (B2C/PLG) who want to raise ADR quality on their own without waiting for a team process.

## User & Persona

### Primary persona

Tech lead or architect on a product team, using the product **individually** (B2C/PLG — own account, pays themselves, independent of team tooling). They reach for the product when they need to write an ADR and want the first draft complete and concise enough that a collaborator's review does not slide on formal gaps — and goes straight to the substance of the decision.

## Success Criteria

### Primary

1. User completes the full flow in one session: **login → new ADR from template → fill in content → publish for review → AI review returns annotations → user improves ADR → publishes as `proposed`** (`draft` → `in_review` → `after_review` → `proposed`).
2. After **one** AI review iteration the user receives a **shorter and more complete** ADR than before review.

### Secondary

- User returns after days and browses their ADR history (card view + opening an existing document) — proof that the product has lasting value, not just a one-shot.

### Guardrails

- **≥80% of AI reviews** correctly detect missing required ADR sections (context, decision, alternatives, consequences).
- Shortening suggestions are **concrete and actionable** — each flagged spot has a proposal for how to shorten it.
- **No draft loss** while editing an ADR; refresh, tab close, or session expiry must not erase the user's latest saved work.

## User Stories

### US-01: Creates ADR, receives AI review, publishes as `proposed`

- **Given** a logged-in user on their ADR list
- **When** they create a new ADR from the markdown starter template (pre-filled with `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences` headings), fill in the content under each heading in the markdown editor, click "Publish for review", wait for the review to complete, read the annotations (missing sections, inconsistencies, conciseness suggestions), edit the ADR inline in `after_review` status, and click "Publish"
- **Then** the ADR transitions through statuses `draft` → `in_review` → `after_review` → `proposed`

#### Acceptance Criteria

- In `after_review` the user sees at least one actionable annotation for each type of problem the AI detected
- Editing in `after_review` does NOT trigger another AI review
- Clicking "Publish" from `after_review` transitions the ADR to `proposed` without an additional review

### US-02: Returns after days and opens an existing ADR from history

- **Given** a logged-in user with at least one ADR created in a previous session
- **When** they navigate to their ADR list
- **Then** they see the complete list of their own ADRs regardless of status (`draft`, `in_review`, `after_review`, `proposed`), with clear status indicators, and can open any one for viewing or further editing (where the status permits editing)

### US-03: Registration and immediate access

- **Given** a person who has never had an account opens the registration page
- **When** they enter an email and password and click "Register"
- **Then** their account is created and they can log in to the main application immediately (no email verification step in MVP)

### US-04: Edits ADR after AI review without re-review

- **Given** an ADR owned by the user in `after_review` status with AI annotations visible
- **When** the user edits ADR markdown content inline (e.g., adds a missing section flagged by AI, shortens a verbose fragment) and then saves (save-on-blur, save-on-unload, or explicit "Publish")
- **Then** the changes are preserved, the status does NOT revert to `draft` or `in_review`, and clicking "Publish" transitions the ADR to `proposed` without re-triggering AI review

## Functional Requirements

### Account & access

- FR-001: User can register a new account using email and password through self-service signup. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written.
- FR-002: ~~User can verify their email address by clicking a verification link before gaining access to the application.~~ **REMOVED from MVP.**
  > Socrates: Counter-argument accepted: "MVP B2C/PLG with no payments — spam account cost is low, verification is excessive caution." Resolution: dropped from MVP; reintroduce post-MVP if spam becomes a real problem.
- FR-003: User can log in to the application using email and password. Priority: must-have
  > Socrates: Counter-argument accepted: "Explicit logout in MVP is unnecessary — session expiry is enough." Resolution: removed logout from scope; FR retained for login only.

### ADR authoring

- FR-004: User can create a new ADR document from a standardized markdown starter template that pre-fills required section headings (`## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences`) as the structural contract the AI review parses against. Priority: must-have
  > Socrates: Counter-argument accepted (architecture pivot): "Structural fields are unnecessary — a single markdown section with guidelines in a comment achieves the same effect at lower cost." Resolution: pivoted from field-based template to markdown-only editor with starter template; AI parses markdown headings to validate required sections.
- FR-005: User can edit the ADR markdown content in a web editor in any status except `in_review`. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written.
- FR-006: User's ADR edits are persisted by save-on-blur (when focus leaves the editor) and by save-on-unload (when the user closes the tab or refreshes), so a draft is not lost on browser close, refresh, or session expiry. Priority: must-have
  > Socrates: Counter-argument accepted: "Save-on-blur is simpler and sufficient for MVP — full continuous autosave is excessive complexity (debounce, conflict, network failure)." Resolution: revised from continuous autosave to save-on-blur + save-on-unload; equivalent against Guardrail "no draft loss".

### ADR lifecycle

- FR-007: User can advance an ADR through four statuses: `draft` → `in_review` → `after_review` → `proposed`. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written; 4-status model negotiated explicitly in Phase 4.
- FR-008: User can trigger AI review by clicking "Publish for review", which transitions ADR from `draft` to `in_review`. AI review runs exactly once per ADR in MVP. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written; re-review and quota-based variants deferred post-MVP.
- FR-009: User can click "Publish" from `after_review` to transition ADR to `proposed`. No AI re-review is triggered. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written; user retains control and accountability for publishing post-review.

### AI review output

- FR-010: User receives AI feedback annotations identifying missing required ADR sections (context, options, decision, status, consequences) when ADR enters `after_review`. Priority: must-have
  > Socrates: Counter-argument considered: "Section set should be configurable per organization-specific ADR convention." Resolution: MVP keeps fixed 5 sections; configurable conventions (analogous to per-user rules / system prompts) deferred to post-MVP. Captured as forward-looking note.
- FR-011: User receives AI feedback identifying inconsistencies in the ADR content when ADR enters `after_review`. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written.
- FR-012: User receives ADR conciseness analysis with actionable suggestions on what specifically to shorten when ADR enters `after_review`. Priority: must-have
  > Socrates: Counter-argument considered: none stood. Resolution: kept as written; "actionable" Guardrail is the binding quality bar.

### History

- FR-013: User can browse their own ADRs as a card view (each card showing at minimum the title, current status, and last edited timestamp) and open any one for viewing or further editing (where editing is allowed by status). Priority: must-have
  > Socrates: Counter-argument accepted: "Cards are clearer than a list — they show title, status, and last edited date at a glance." Resolution: changed from flat list to card view; filtering/search deferred post-MVP.

### Nice-to-have

- FR-014: User can receive an email notification when an AI review completes. Priority: nice-to-have
  > Socrates: Counter-argument considered: none stood (nice-to-have already deferred). Resolution: kept as nice-to-have; may be promoted if review latency grows beyond user tolerance.

### Lifecycle management

- FR-015: User can remove their own ADR from their active list. A removed ADR no longer appears in the user's card view; in MVP the user cannot permanently destroy the record. Priority: must-have
  > Note: Added post-Socrates round as a consequence of Phase 5 retention decision ("forever until user deletes"). No separate Socrates round; hide-from-view chosen over permanent destruction for safety (reversible).

## Non-Functional Requirements

- **Section gap detection accuracy:** At least 80% of AI reviews correctly detect missing required ADR sections (context, decision, alternatives, consequences).
- **Annotation actionability:** Each detected issue (missing section, inconsistency, fragment to shorten) has at least one associated concrete corrective action proposal.
- **No draft loss:** After refresh, tab close, browser crash, or session expiry, the user can recover the latest saved ADR content without losing substantive edits.
- **Per-user data isolation:** No user can access another user's ADR through the application by any means (direct navigation, bookmark, or guessed link).
- **Browser support:** The application works on current versions of major desktop browsers (latest two major releases).
- **Data retention:** User ADRs are stored indefinitely until the user consciously removes them from their active list; in MVP, removal hides the ADR from the user — permanent destruction is out of scope.

## Business Logic

The product **evaluates ADR content for the presence of 5 required sections (context, options, decision, status, consequences), internal inconsistencies, and conciseness, and returns annotations to the user along with concrete shortening suggestions.**

**Input:** ADR content written by the user in markdown, with section headings (`## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences`) — in the state it was in when published via the "Publish for review" action.

**Output:** the same ADR extended with three classes of annotations: (a) list of missing or empty sections, (b) list of detected inconsistencies with location in the text, (c) list of specific fragments to shorten along with proposed more concise wording.

**When the user sees the result:** after the ADR transitions from `in_review` to `after_review` — annotations are visible inline in the editor; the user can address them with edits, then publish the ADR to `proposed` status.

## Access Control

- **Login:** email + password. Each user creates their own account through open self-service registration. After registration they can use the application immediately — email verification is out of MVP (Socrates FR-002 decision).
- **Session:** no explicit logout in MVP; session expiry is sufficient (Socrates FR-003 decision).
- **Permission model:** flat — single user type, no roles in MVP.
- **Data isolation:** per-user — each user sees only their own ADRs. No sharing, no public ADRs, no share-by-link in MVP.
- **Unauthorized access:** attempting to reach a route behind login redirects to the login screen.

## Non-Goals

### Functional non-goals

- **No automatic ADR generation from repository code** — from seed; the product is a tool for AUTHORING ADRs, not a generator.
- **No integration with external code-hosting platforms** for fetching architectural context — from seed; all context is supplied by the author in ADR content.
- **No real-time multi-user collaboration** — from seed; B2C/PLG, one author per ADR.
- **No advanced approval workflow** (comments, roles, approval flow) — from seed; AI review replaces formal human approval in MVP.
- **No automatic committing of ADRs to the user's repository** — from seed; the product is hosted SaaS, not a repo agent.
- **No re-review after ADR edits** — review runs once in the ADR lifecycle (draft → in_review); further edits after `after_review` do not trigger a new review.
- **No per-user configurable ADR conventions** — 5 sections (context, options, decision, status, consequences) are hard-coded; organization-specific convention packs deferred post-MVP.
- **No filtering or search in the ADR list** — card view without filters; sufficient for small scale (< 100 ADRs per user).
- **No `accepted` / `superseded` statuses** — MVP has only 4 statuses (draft → in_review → after_review → proposed); full ADR decision lifecycle deferred post-MVP.
- **No password reset in MVP** — a user who forgets their password loses account access (conscious decision; contact support or recreate account).
- **No permanent ADR destruction** — users can remove ADRs from their active view only; records are retained.
- **No shared workspaces / team feature** — B2C/PLG only, one user = one isolated space.
- **No ADR export** (markdown download, PDF) — ADRs live in the product, do not leave it in MVP.

### Non-functional non-goals

- **No visible progress / no hard SLA for AI review duration** — conscious MVP decision; user waits without a progress indicator; UX risk acceptance recorded in Phase 5.

## Open Questions

1. **Does save-on-blur + save-on-unload actually suffice against draft loss?** — Owner: user. By: verification before MVP lock. Block: no (FR-006 stands, but if QA finds an edge case e.g. missing unload trigger on OS crash, may require closing with debounced autosave).
2. **What happens to a user who forgot their password?** — Owner: user. By: post-MVP. Block: no (conscious non-goal, but account retention risk — worth having a manual recovery path via support).
3. **Will "no visible progress" for AI review cause mass tab closures during review?** — Owner: user. By: first pilot wave. Block: no (ready to promote FR-014 / add visible progress feedback if the problem is real).