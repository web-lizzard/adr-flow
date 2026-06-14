---
date: 2026-06-14T15:54:00+02:00
researcher: Cursor
git_commit: b07acc35548859ee14e879062a58d9eba9a16440
branch: feature/persistence-scaffold-f02
repository: adr-flow
topic: "Propose the domain aggregates before data schema modeling (F-02 persistence scaffold)"
tags: [research, domain-model, aggregates, ddd, event-sourcing, persistence-scaffold]
status: complete
last_updated: 2026-06-14
last_updated_by: Cursor
last_updated_note: "Added Forward-compatibility notes (re-review, customizable rules, orgs/workspaces incl. user_id-as-ownership-scope)"
---

# Research: Domain aggregates for adr-flow (before F-02 schema modeling)

**Date**: 2026-06-14T15:54:00+02:00
**Researcher**: Cursor
**Git Commit**: b07acc35548859ee14e879062a58d9eba9a16440
**Branch**: feature/persistence-scaffold-f02
**Repository**: adr-flow

## Research Question

Propose the domain aggregates based on `context/foundation/prd.md` and `context/foundation/application-architecture.md`, before doing data-schema modeling for the F-02 persistence scaffold (`context/changes/github-issues/F-02-persistence-scaffold.md`).

## Summary

The MVP has **two aggregates**: **`User`** and **`ADR`**. This matches the `aggregate_type` values (`user`, `adr`) and the six domain events already named in the architecture doc (`application-architecture.md:87`, `:110`).

- **`User`** is a thin write-once aggregate: it is created at registration and never transitions afterward (no logout, no password reset, no email verification in MVP). Its only domain event is `UserRegistered`.
- **`ADR`** is the rich aggregate and the real consistency boundary. It owns the four-status lifecycle (`draft → in_review → after_review → proposed`), the markdown content, the AI review annotations, and the soft-delete flag. Its events are `ADRCreated`, `ADRContentUpdated`, `ADRSubmittedForReview`, `AIReviewCompleted`, `ADRPublished`, `ADRSoftDeleted`.

The most consequential modeling decision is **whether AI review/annotations are a separate aggregate or part of `ADR`**. The recommendation for MVP is to **embed annotations inside the `ADR` aggregate** (carried by the `AIReviewCompleted` event, stored as a value-object collection) rather than introducing a `Review` aggregate. Review runs exactly once, is never re-run, and is only ever read in the context of its ADR — so a separate aggregate adds a consistency boundary the MVP never needs. (See [Architecture Insights](#architecture-insights) for the trade-off and the post-MVP trigger to split it out.)

For F-02 specifically: the schema scaffold needs the `events` table plus `users` and `adrs` projections. The aggregate model says the `adrs` projection must carry `user_id`, `title`, `content`, `status`, a soft-delete flag, timestamps, **and** somewhere to hold review annotations (recommended: a JSONB column on `adrs`, not a separate table for MVP). F-02 builds the schema contract only; the aggregate classes themselves land in S-01 (`domain/user/`) and S-02 (`domain/adr/`).

## Detailed Findings

### Aggregate boundary analysis

The architecture pre-commits the boundaries and the vocabulary:

- `aggregate_type` is `adr` or `user` ([application-architecture.md:87](context/foundation/application-architecture.md)).
- Domain events listed: `UserRegistered`, `ADRCreated`, `ADRSubmittedForReview`, `AIReviewCompleted`, `ADRPublished`, `ADRSoftDeleted` ([application-architecture.md:110](context/foundation/application-architecture.md)).
- Module layout reserves `domain/user/` and `domain/adr/` ([application-architecture.md:123-124](context/foundation/application-architecture.md)).

This research confirms those two boundaries are correct for the MVP and fills in the missing pieces: value objects, the full event set (the architecture list omits the edit event), invariants, and the state machine.

### Aggregate 1 — `User`

- **Purpose:** owns identity and credentials; the anchor for per-user data isolation.
- **Identity:** `user_id: UUID`.
- **State:** `email`, `password_hash`, `created_at`.
- **Value objects:**
  - `EmailAddress` — validated, normalized (lowercased) email.
  - `PasswordHash` — never stores plaintext (PRD Access Control; [S-01 DoD "Passwords stored securely"](context/changes/github-issues/S-01-account-access.md)).
- **Commands / behaviors:** `RegisterUser` (the only state-changing behavior). Login is authentication only — it verifies credentials and mints a token; it does **not** mutate the aggregate and emits **no** event. No logout (FR-003 / PRD Access Control), no password reset, no email verification (FR-002 removed) in MVP.
- **Events:** `UserRegistered { user_id, email, password_hash, occurred_at }`.
- **Invariants:**
  - Password is always stored hashed.
  - Email is well-formed.
  - **Email uniqueness is a set-based invariant** — it cannot be enforced *inside* a single `User` aggregate. Enforce it with a unique constraint on the `users` projection plus a pre-insert lookup in the `RegisterUser` handler. Flag this in the F-02 schema (unique index on `users.email`).
- **Lifecycle:** created once; no further transitions in MVP.

### Aggregate 2 — `ADR`

- **Purpose:** the document the product exists to improve; the real consistency boundary holding content, lifecycle, and review feedback.
- **Identity:** `adr_id: UUID`.
- **Owner reference:** `user_id: UUID` held **by value** (reference another aggregate by identity, not by object). Ownership is enforced in the application layer (command/query checks owner) and via per-user filtering in queries — satisfies NFR: Per-user data isolation.
- **State:** `user_id`, `title`, `content` (markdown), `status`, `annotations` (review result, empty until reviewed), `is_deleted` (soft-delete flag), `created_at`, `updated_at`, `reviewed_at?`.
- **Value objects:**
  - `AdrStatus` — enum `draft | in_review | after_review | proposed` (FR-007).
  - `AdrTitle`.
  - `AdrContent` — the markdown body; seeded from the fixed starter template with the five headings `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences` ([S-02 starter template](context/changes/github-issues/S-02-draft-authoring-persistence.md); FR-004).
  - `ReviewAnnotation` — `{ kind, location?, message, suggestion? }` where `kind ∈ { missing_section, inconsistency, conciseness }` (FR-010 / FR-011 / FR-012). Conciseness annotations carry a concrete `suggestion` (PRD Annotation actionability guardrail).
  - `ReviewResult` — the collection of `ReviewAnnotation` plus `reviewed_at` and (optionally) a snapshot of the content that was reviewed.
- **Commands / behaviors → events:**
  - `CreateAdr` → `ADRCreated` (status starts `draft`, content = starter template).
  - `UpdateAdrContent` → `ADRContentUpdated` *(event not named in the architecture list but required by FR-005/FR-006 save-on-blur + save-on-unload; surface this gap).*
  - `SubmitAdrForReview` → `ADRSubmittedForReview` (`draft → in_review`).
  - `CompleteAiReview` → `AIReviewCompleted` (`in_review → after_review`, carries the annotation set). Emitted through the aggregate by the async `RunAiReview` handler so the invariant (only complete from `in_review`) holds ([application-architecture.md:114](context/foundation/application-architecture.md)).
  - `PublishAdr` → `ADRPublished` (`after_review → proposed`).
  - `SoftDeleteAdr` → `ADRSoftDeleted` (sets `is_deleted`; allowed from any status).
- **Invariants / business rules:**
  - **Status machine** (forward-only):
    - `draft → in_review` only via `SubmitAdrForReview` (FR-008).
    - `in_review → after_review` only via `AIReviewCompleted` (FR-007).
    - `after_review → proposed` only via `PublishAdr`; publish triggers **no** re-review (FR-009 / US-04).
  - **Review runs exactly once** — `SubmitAdrForReview` is only valid from `draft`; there is no path back into `in_review` (FR-008; PRD Non-Goal "No re-review").
  - **Editing is blocked in `in_review`** and allowed otherwise (FR-005). See open question on whether `proposed` is literally editable.
  - **Soft-delete is orthogonal** to status: an ADR can be removed from any status; a deleted ADR is hidden from queries and not reachable (FR-015; NFR: Data retention — record retained, never destroyed in MVP).
  - **Owner-only operations** — every command validates `user_id` ownership (NFR: Per-user data isolation).

### Domain events ↔ slices ↔ FRs

| Event | Aggregate | Introduced by slice | Drives FR |
|---|---|---|---|
| `UserRegistered` | User | S-01 | FR-001 |
| `ADRCreated` | ADR | S-02 | FR-004 |
| `ADRContentUpdated` | ADR | S-02 (and S-05 edits) | FR-005, FR-006 |
| `ADRSubmittedForReview` | ADR | S-04 | FR-007, FR-008 |
| `AIReviewCompleted` | ADR | S-04 | FR-007, FR-010/011/012 |
| `ADRPublished` | ADR | S-05 | FR-007, FR-009 |
| `ADRSoftDeleted` | ADR | S-06 | FR-015 |

### ADR state machine

```
            CreateAdr
               │
               ▼
   ┌───────► draft ──────SubmitAdrForReview─────► in_review
   │           │                                      │
UpdateAdrContent│ (edit allowed)                 AIReviewCompleted
   │           │                                      │
   │           ▼                                      ▼
   └──── after_review ◄──────────────────────── after_review
               │   ▲                            (annotations attached)
        UpdateAdrContent (edit allowed, no re-review)
               │
           PublishAdr
               │
               ▼
            proposed

   SoftDeleteAdr: valid from ANY status → sets is_deleted (orthogonal)
```

## Code References

The backend domain layer does not exist yet — only the FastAPI scaffold is present, so these are the locations the model will land in (per the reserved module layout), not existing implementations:

- `backend/main.py` — current backend is the `GET /health` scaffold only; no domain/persistence code.
- `backend/tests/test_health.py` — only existing test.
- `context/foundation/application-architecture.md:87` — `aggregate_type` values (`adr`, `user`).
- `context/foundation/application-architecture.md:110` — canonical domain-event names.
- `context/foundation/application-architecture.md:99-100` — projection tables `users` / `adrs` and their columns.
- `context/foundation/application-architecture.md:123-139` — reserved module layout (`domain/user/`, `domain/adr/`, `persistence/projections/`).
- `.cursor/rules/backend-architecture.mdc:20-21` — `adrs.status` is a projection of events, never set arbitrarily; routers never mutate projections.
- `.cursor/rules/backend-application.mdc:9-23` — one use case per command/query file (`{Name}Command` + `{Name}CommandHandler`).

## Architecture Insights

- **Two aggregates, asymmetric weight.** `User` is write-once; `ADR` carries all the interesting behavior. Don't over-model `User`.
- **Reference across aggregates by identity.** `ADR` holds `user_id` (a UUID), not a `User` object. Ownership consistency is an application-layer concern, not an in-aggregate invariant.
- **Set-based invariants live in the projection.** Email uniqueness can't be enforced inside `User`; it belongs to a unique constraint on the `users` projection. F-02 should include it.
- **Annotations: embed vs. separate `Review` aggregate (the key call).**
  - *Recommended (MVP): embed in `ADR`.* The `AIReviewCompleted` event carries the annotation collection; the `ADR` aggregate stores it as a `ReviewResult` value object. Rationale: review runs **once**, is never re-run (PRD Non-Goal), and annotations are only ever read in the ADR's `after_review` context ([S-04 business logic](context/changes/github-issues/S-04-first-ai-review-annotations.md)). One consistency boundary, simplest event stream, fewer tables.
  - *Alternative: a `Review` aggregate* with its own id/lifecycle. Only justified post-MVP if re-review, review history/versioning, or review quotas arrive (all explicitly parked in `roadmap.md:192-193`). **Trigger to revisit:** when "re-review after edits" leaves the Parked list.
- **`AIReviewCompleted` must flow through the aggregate.** Even though the async `RunAiReview` handler produces it as a side effect ([application-architecture.md:114](context/foundation/application-architecture.md)), routing it through the `ADR` aggregate preserves the `in_review → after_review` invariant and keeps the handler idempotent for startup replay ([application-architecture.md:104-106](context/foundation/application-architecture.md)).
- **The architecture's event list is missing the edit event.** `ADRContentUpdated` is required by FR-005/FR-006 (save-on-blur / save-on-unload) but is absent from `application-architecture.md:110`. Recommend adding it; otherwise edits have no event in an event-sourced model.

## Forward-compatibility notes (post-MVP optionality)

These are **not MVP scope**. They record why the proposed two-aggregate model does not foreclose three plausible futures, and the cheapest thing (if any) to do now to keep that optionality. The general guarantee underneath all three: event sourcing decouples immutable facts (the `events` table, append-only — `application-architecture.md:93`) from rebuildable read models, so aggregate boundaries and projections can evolve as long as the events are preserved.

- **Re-review by AI later (PRD Non-Goal today; parked `roadmap.md:192`).** Not blocked. "Review runs once" is an *invariant in the `ADR` aggregate*, not a structural limit — loosening it is a code change, not a migration. Re-review history is also safe: every `AIReviewCompleted` is already in the event log, so even though the embedded `ReviewResult` projection holds only the latest result, a richer `reviews` read model can be rebuilt from events. **Trigger to split a `Review` aggregate:** only when a review needs its *own* identity/lifecycle (commentable, accept/reject, referenced independently of its ADR) — not merely re-run-and-keep-history.

- **Customizable ADR rules later (PRD Non-Goal today; parked `roadmap.md:193`).** Not blocked. In MVP the five required sections are an implementation detail of the review handler / `domain/adr` validation, **not** persisted data and **not** `ADR` aggregate state (an ADR is reviewed *against* rules; it does not *own* them). To stay free: keep the rule definition out of the `ADR` aggregate, and when customization arrives a `RuleSet` / convention entity (likely owned by the ownership scope below) feeds a `rule_set_id` into the review handler. Cheap forward-looking step (S-04, **not** F-02): record which ruleset/version produced annotations in the `AIReviewCompleted` payload.

- **Organizations / workspaces later (PRD Non-Goal `prd.md:174`).** Not blocked, and this is the only one with a real migration cost if ignored — so treat it conceptually now without adding scope. **Conceptualize `adrs.user_id` as the *ownership scope*, which in MVP happens to equal the user.** When workspaces arrive, scope becomes `workspace_id` and `user_id` demotes to "author" — an *additive* migration (add `workspace_id`, backfill each user's personal workspace), not a structural rewrite, precisely because `ADR` references its owner **by a single identity** rather than embedding user data. The second protection is to keep per-user isolation enforcement in **one seam** (the command/query ownership check) so there is a single place to change "filter by user" → "filter by workspace membership". **Do not** add a `workspaces` table or `workspace_id` column in F-02 — that is speculative scope; the optionality comes from the aggregate model, not from pre-built empty tables.

## Implications for F-02 schema modeling

F-02 delivers the schema contract only (events table + projections + ports + bootstrap skeleton + empty dispatcher — [application-architecture.md:181](context/foundation/application-architecture.md)); aggregate classes come in S-01/S-02. The aggregate model dictates these columns:

- **`events`** (write-side source of truth): `id`, `aggregate_type` (`user`|`adr`), `aggregate_id`, `event_type`, `payload` (JSONB), `occurred_at`, `processed_at` (NULL until handlers complete, for startup replay) — matches [application-architecture.md:83-91](context/foundation/application-architecture.md).
- **`users`** projection: `id`, `email` (**unique index** — set-based invariant), `password_hash`, `created_at`.
- **`adrs`** projection: `id`, `user_id` (FK/owner, indexed for per-user listing), `title`, `content` (markdown text), `status` (enum/text of the four values), `is_deleted` (soft-delete flag, default false), `created_at`, `updated_at`. Plus a place for review output.
- **Annotation storage decision (flows from the embed recommendation):** store the review result as a **`review_annotations JSONB`** column on `adrs` (nullable, populated on `AIReviewCompleted`) rather than a separate `adr_annotations` table. Justification: small data volume (PRD `target_scale.data_volume: small`), annotations are always read with their ADR, and the embed model treats them as a value object — a separate table would imply a separate identity the MVP doesn't need. Revisit if a `Review` aggregate is later split out.

These are recommendations for the schema; the binding decisions belong in `/plan persistence-scaffold`.

## Historical Context (from prior changes)

- `context/changes/github-issues/F-02-persistence-scaffold.md` — F-02 scope: minimal `User`/`ADR` schema contract with `user_id`, four statuses, markdown content, timestamps, soft-delete flag; explicitly **not** a full data layer.
- `context/changes/github-issues/S-01-account-access.md` — `User` entity must exist before auth; passwords hashed.
- `context/changes/github-issues/S-02-draft-authoring-persistence.md` — fixed starter template (five headings); save-on-blur + save-on-unload.
- `context/changes/github-issues/S-04-first-ai-review-annotations.md` — review I/O: three annotation classes; review visible at `after_review`; runs once.
- `context/changes/github-issues/S-05-publish-after-review.md` — edit in `after_review` without re-review; publish → `proposed`.
- `context/changes/github-issues/S-06-remove-adr-from-active-list.md` — soft-delete exercised here; record retained.
- `context/foundation/roadmap.md:192-193` — re-review and configurable conventions are parked (post-MVP), which is why a single `ADR` aggregate suffices now.

## Related Research

- None yet — this is the first research artifact under `context/changes/persistence-scaffold/`.

## Open Questions

1. **Is `proposed` literally editable?** FR-005 says "any status except `in_review`", which permits editing a `proposed` ADR, but the slices only exercise editing in `draft` and `after_review`. Confirm whether `proposed` should be terminal (read-only) or editable. Owner: user.
2. **Does the architecture's domain-event list need `ADRContentUpdated` added?** Recommended yes; confirm before the model is implemented in S-02.
3. **Annotation storage — JSONB column vs. separate table.** Recommendation is JSONB on `adrs`; confirm during `/plan persistence-scaffold` against any future need to query annotations independently.
4. **Does a soft-deleted ADR keep its `user_id` and status, or only flip `is_deleted`?** Recommendation: flip the flag only (full record retained per NFR: Data retention); confirm in plan.
