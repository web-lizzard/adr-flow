---
project: adr-flow
context_type: greenfield
created: 2026-05-19
updated: 2026-05-19
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  gray_areas_resolved:
    - topic: moment
      decision: first ADR draft + PR review + onboarding + pulling other architects away for formal review
    - topic: cost_today
      decision: many review rounds from collaborators; decisions stretch out by days/weeks
    - topic: pain_category
      decision: workflow friction + coordination overhead + missing capability + standardization gap + knowledge loss
    - topic: insight
      decision: existing ADR tools do storage/scaffolding only; LLMs are only now good enough for structured docs; template→AI review→fix loop as a product does not exist; ADR market perceived as narrow
    - topic: primary_persona_scope
      decision: individual tech leads from different companies, B2C/PLG, own account
    - topic: auth_method
      decision: email + password
    - topic: role_model
      decision: flat — single user type, no roles
    - topic: data_isolation
      decision: per-user — each user sees only their own ADRs
    - topic: signup_model
      decision: open self-service registration
    - topic: email_verification
      decision: email verification required at registration (superseded — removed in Socrates FR-002)
    - topic: mvp_flow
      decision: create + AI review + status lifecycle + ADR history
    - topic: first_session_actions_to_value
      decision: 5 steps to first value (login → new ADR → fill in → save → review)
    - topic: timeline_feasibility
      decision: 3 weeks after-hours; author confirms feasibility
    - topic: autosave
      decision: Guardrail — no draft loss must be in MVP (autosave or equivalent)
    - topic: secondary_scope
      decision: ADR history only as Secondary; email notification after review deferred to FR nice-to-have
    - topic: adr_lifecycle_model
      decision: four statuses in MVP — draft → in_review → after_review → proposed; accepted/superseded out of MVP
    - topic: review_trigger_semantics
      decision: AI review once per ADR in MVP, triggered by "Publish for review" on draft → in_review transition
    - topic: publish_after_review
      decision: "Publish" from after_review always moves to proposed, no re-review
    - topic: edit_in_after_review
      decision: inline editing in after_review, no return to draft
    - topic: fr_count_scope
      decision: 14 FRs (13 must-have + 1 nice-to-have email notification); password reset / delete / search omitted from MVP
    - topic: socrates_fr002_email_verification
      decision: FR-002 removed from MVP after Socrates (spam account cost low, verification excessive); access is immediate after signup
    - topic: socrates_fr003_logout
      decision: FR-003 narrowed to "login only" — logout removed, session expiry sufficient
    - topic: socrates_fr004_markdown_pivot
      decision: pivot from structural fields to markdown-only editor with starter template (H2 section headings as contract for AI review)
    - topic: socrates_fr005_editor
      decision: FR-005 kept as written; naming only changed (markdown content instead of field values)
    - topic: socrates_fr006_save_on_blur
      decision: changed from continuous autosave to save-on-blur + save-on-unload; equivalent to Guardrail no draft loss
    - topic: socrates_fr010_section_set
      decision: 5 fixed sections in MVP; per-user configurability (a la cursor rules / system prompts) deferred post-MVP
    - topic: socrates_fr013_cards
      decision: FR-013 changed from flat list to card view (title + status + last edited date); filtering/search post-MVP
    - topic: business_logic_oneliner
      decision: product evaluates ADR against 5 sections + inconsistencies + conciseness; returns annotations and shortening suggestions
    - topic: nfr_privacy
      decision: strict per-user isolation — no user can access another user's ADR by any path
    - topic: nfr_browser_support
      decision: latest 2 majors of major desktop browsers
    - topic: nfr_retention
      decision: forever until user removes ADR from active list (FR-015 added)
    - topic: nfr_review_latency
      decision: no SLA, no visible progress (consciously accepted UX risk); moved to Non-Goals in Phase 6
    - topic: fr015_remove_from_list
      decision: FR-015 added post-Socrates as consequence of retention NFR; hide from active view (not permanent destruction) for safety
    - topic: product_type
      decision: web-app
    - topic: target_scale_users
      decision: small
    - topic: scale_socratic_100x
      decision: at 100x scale, per-organization rule configuration needed (different ADR conventions); captured in Vision Scale note
    - topic: hard_deadline
      decision: no deadline
    - topic: after_hours_only
      decision: true
    - topic: non_goals
      decision: 13 functional non-goals (5 from seed + 8 from discussion) + 1 non-functional (no SLA/progress); omitted password reset, permanent ADR destruction, team workspaces, export, configurable conventions, search, accepted/superseded, re-review
    - topic: forward_tech_stack_notes
      decision: none — stack selection deferred to 10x-tech-stack-selector
  frs_drafted: 14
  quality_check_status: accepted
---

## Seed idea

Main problem
Writing Architecture Decision Records is often inconsistent, overly verbose, and omits key elements such as context, alternatives, decision, and consequences. Teams lose the value of ADRs as a short, readable record of important architectural decisions.

Minimum feature set
Creating ADRs in a single, standardized template based on fields such as context, options, decision, status, and consequences.

Web editor for saving, browsing, and editing ADRs.

AI review module that checks whether the document meets the qualities of a good ADR and flags missing sections or inconsistencies.

Document length and conciseness analysis with shortening suggestions, because ADRs should be short and to the point.

Simple version history or statuses, e.g. proposed, accepted, superseded.

Out of MVP scope
Automatic writing of a full ADR from repository code.

Integrations with external code-hosting platforms for fetching project architectural context.

Real-time multi-user collaboration.

Advanced approval workflow with comments, roles, and approval flow.

Automatic committing of ADRs to the user's repository.

Success criteria

At least 80% of AI assessments correctly detect missing required ADR sections such as context, decision, alternatives, and consequences.

Users are able to produce a shorter, more complete ADR after one AI review iteration.

## Vision & Problem Statement

A tech lead or architect on a product team writing an ADR — when drafting for the first time, during PR review, or while onboarding new people — faces inconsistent documents that are too verbose or too short and omit key sections (context, alternatives, decision, consequences). The cost today falls on others: the author pulls collaborating architects into many rounds of **formal** review (missing sections, overly granular content), stretching decisions by days or weeks and wasting their time on non-substantive issues.

Existing ADR tooling focuses on storage and scaffolding, not document quality assessment. The "template → AI review → fix" loop as a ready-made product does not exist — everyone assumes a human reviewer enforces ADR quality. At the same time, LLMs are only now good enough to evaluate structured docs like ADRs, and the ADR-as-product market is perceived as too narrow for anyone to assemble into one product — which leaves an open niche for individual tech leads (B2C/PLG) who want to raise ADR quality on their own without waiting for a team process.

**Scale note (Socrates):** At 100x scale, a fixed set of 5 sections will not suffice — different organizations use different ADR conventions. A need will emerge for configurable review rules per organization / per workspace, likely in a model similar to per-user rules / system prompts. Out of MVP.

## User & Persona

### Primary persona

Tech lead or architect on a product team, using the product **individually** (B2C/PLG — own account, pays themselves, independent of team tooling). They reach for the product when they need to write an ADR and want the first draft complete and concise enough that a collaborator's review does not slide on formal gaps — and goes straight to the substance of the decision.

## Access Control

- **Login:** email + password. Each user creates their own account through open self-service registration. After registration they can use the application immediately — email verification is out of MVP (Socrates FR-002 decision).
- **Session:** no explicit logout in MVP; session expiry is sufficient (Socrates FR-003 decision).
- **Permission model:** flat — single user type, no roles in MVP.
- **Data isolation:** per-user — each user sees only their own ADRs. No sharing, no public ADRs, no share-by-link in MVP.
- **Unauthorized access:** attempting to reach a route behind login redirects to the login screen.

## Success Criteria

### Primary

1. User completes the full flow in one session: **login → new ADR from template → fill in content → publish for review → AI review returns annotations → user improves ADR → publishes as `proposed`** (`draft` → `in_review` → `after_review` → `proposed`).
2. After **one** AI review iteration the user receives a **shorter and more complete** ADR than before review.

### Secondary

- User returns after days and browses their ADR history (card view + opening an existing document) — proof that the product has lasting value, not just a one-shot.

### Guardrails

- **≥80% of AI reviews** correctly detect missing required ADR sections (context, decision, alternatives, consequences).
- Shortening suggestions are **concrete and actionable** — each flagged spot has a proposal for how to shorten it.
- **No draft loss** while editing an ADR (save-on-blur + save-on-unload or equivalent mechanism).

## Timeline Budget

- `mvp_weeks`: 3
- `after_hours_only`: true (confirmed in Phase 6)
- `hard_deadline`: none (confirmed in Phase 6)

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

## Business Logic

The product **evaluates ADR content for the presence of 5 required sections (context, options, decision, status, consequences), internal inconsistencies, and conciseness, and returns annotations to the user along with concrete shortening suggestions.**

**Input:** ADR content written by the user in markdown, with section headings (`## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences`) — in the state it was in when published via the "Publish for review" action.

**Output:** the same ADR extended with three classes of annotations: (a) list of missing or empty sections, (b) list of detected inconsistencies with location in the text, (c) list of specific fragments to shorten along with proposed more concise wording.

**When the user sees the result:** after the ADR transitions from `in_review` to `after_review` — annotations are visible inline in the editor; the user can address them with edits, then publish the ADR to `proposed` status.

## Non-Functional Requirements

- **Section gap detection accuracy:** At least 80% of AI reviews correctly detect missing required ADR sections (context, decision, alternatives, consequences).
- **Annotation actionability:** Each detected issue (missing section, inconsistency, fragment to shorten) has at least one associated concrete corrective action proposal.
- **No draft loss:** Content of the ADR being edited is persisted when the editor field loses focus and when the window is closed; the browser recovers the last saved state after an unintended refresh/crash.
- **Per-user data isolation:** No user can access another user's ADR through the application by any means (direct navigation, bookmark, or guessed link).
- **Browser support:** The application works on current versions of major desktop browsers (latest two major releases).
- **Data retention:** User ADRs are stored indefinitely until the user consciously removes them from their active list; in MVP, removal hides the ADR from the user — permanent destruction is out of scope.

## Product Framing

- `product_type`: web-app
- `target_scale`:
  - `users`: small
  - `qps`: low
  - `data_volume`: small
- `timeline_budget`:
  - `mvp_weeks`: 3
  - `hard_deadline`: null
  - `after_hours_only`: true

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

## Forward: technical-roadmap

Implementation details routed out of PRD-mapped sections for downstream stack selection / build planning:

- **Competitive context:** existing ADR tools include madr, log4brains, adr-tools — storage/scaffolding only, no quality-assessment loop.
- **ADR convention references:** at scale, organizations may expect madr-, log4brains-, or custom-style section sets; MVP hard-codes 5 sections.
- **Deletion model:** soft-delete (hidden from card view, content retained in storage); no hard-erase / permanent destruction in MVP.
- **Data isolation enforcement:** must hold at UI, URL, and API layers — no cross-user access by any path.
- **Browser matrix:** latest 2 major releases of Chrome, Firefox, Safari, and Edge on desktop.
- **Code-hosting integrations:** no GitHub/GitLab (or similar) fetch of repo architectural context in MVP.
- **Review wait UX:** if tab-closure during review becomes a problem, candidate mitigations include email notification (FR-014) or a progress indicator (e.g. spinner).

## Quality cross-check

Phase 7 — soft-gate cross-check against required greenfield elements:

- **Access Control:** present (email+password login, flat model, per-user isolation, session expiry).
- **Business Logic:** present (one-sentence rule + 3 paragraphs input/output/when user sees result; not empty-CRUD).
- **Project artifacts:** present (shape-notes.md with valid checkpoint frontmatter).
- **Timeline-cost ack:** present (`mvp_weeks: 3`; user confirmed feasibility in Phase 3, no separate acknowledgment required).
- **Non-Goals:** present (13 functional + 1 non-functional non-goal; rich and concrete).
- **Preserved behavior:** n/a (greenfield).

**Result:** all required elements present. `quality_check_status: accepted`. No gaps to mirror into `## Open Questions` (Open Questions exists independently with 3 consciously accepted risks from phases 3, 5, and 6).