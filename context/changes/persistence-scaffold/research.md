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
last_updated_note: "Added follow-up research for applying migrations to self-hosted Postgres in CI"
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

## Follow-up Research 2026-06-14T14:47:13+00:00

### Research Question

How to apply migrations to self-hosted Postgres in CI for the `persistence-scaffold` change.

### Summary

The best fit for this repo is **not** a GitHub-hosted runner connecting directly to the production Postgres VM. The production database is intentionally private: the GCP deployment uses a self-hosted Postgres VM on an internal IP, Cloud Run reaches it through Direct VPC egress, and the firewall is scoped to the Cloud Run subnet. GitHub-hosted runners are outside that network, so making them run migrations would require opening the database, adding a bastion/IAP tunnel, or using a self-hosted runner in the VPC.

Recommended approach: **run migrations as a GCP-side deploy step near the app**, preferably a Cloud Run Job (or equivalent one-off Cloud Run execution) that uses the same backend runtime, service account, `DATABASE_URL` Secret Manager secret, and VPC egress settings as the API. GitHub Actions should trigger and wait for that job, then deploy/shift traffic only if migrations pass.

For F-02, choose a migration tool that provides a migration history table and CI checks. Alembic fits the Python/FastAPI/uv stack well: `uv run alembic upgrade head` for applying migrations, `uv run alembic current --check-heads` for asserting a DB is current, and `uv run alembic check` for detecting model/schema drift when autogenerate metadata exists.

### Current Repo State

- `backend/main.py` is still the health-only FastAPI scaffold; no persistence code reads `DATABASE_URL` yet.
- `backend/pyproject.toml` has only FastAPI and Uvicorn dependencies; there is no Postgres driver, SQLAlchemy/SQLModel, Alembic, or plain SQL migration runner yet.
- F-02 explicitly scopes in "Postgres driver and migration tooling" plus the minimal `User` and `ADR` schema contract (`context/changes/github-issues/F-02-persistence-scaffold.md`).
- `Justfile` has dev/test/deploy recipes, but no migration recipe.
- `.github/workflows/deploy-gcp.yml` deploys the API and web on push to `main`, but has no test DB service and no migration step.
- `.pre-commit-config.yaml` runs lint/type gates only; no migration validation hook exists.

### Postgres and Network Constraints

- Local dev Postgres exists in the devcontainer as `postgres:16-alpine`, exposed to the host on port `5435`, with in-container `DATABASE_URL=postgresql://dev:dev@postgres:5432/app`.
- Production Postgres is provisioned by `deploy/gcp/03-gce-postgres.sh` and `deploy/gcp/postgres-vm-setup.sh` on a GCE VM.
- The production app gets `DATABASE_URL` from Secret Manager via `deploy/gcp/run-api.flags`.
- `deploy/gcp/run-api.flags` already configures Direct VPC egress for the API. A migration job should mirror this networking instead of bypassing it from CI.
- `deploy/gcp/README.md` documents the small Postgres shape, including low connection limits. Keep the migration runner single-instance/single-task.

### Recommended CI/CD Shape

Use two different migration paths:

1. **PR/test CI:** run migrations against an ephemeral Postgres service container in GitHub Actions. This validates that the migration set applies cleanly on a fresh database without touching shared infrastructure.
2. **Production deploy:** after GitHub Actions authenticates to GCP through Workload Identity Federation, execute a GCP-side migration job and wait for completion. Only then deploy or shift traffic for the API revision.

The production job should be configured with:

- one task / one instance / low retry count;
- the same service account used by the API, or a narrower migration service account with Secret Manager access;
- the same `DATABASE_URL=db-url:latest` secret;
- the same Direct VPC egress network/subnet settings as the API;
- command equivalent to `cd backend && uv run alembic upgrade head`;
- GitHub Actions `concurrency` for deploys so two migration jobs cannot race.

Cloud Run Jobs are a good operational fit because Cloud Run jobs support one-off task execution, command overrides, Secret Manager environment injection, and Direct VPC egress flags through `gcloud`. Context7-backed docs checked during this follow-up also confirm Alembic supports `upgrade head`, `current --check-heads`, and `check` for CI-oriented validation.

### Options Considered

- **GitHub runner connects directly to Postgres:** poor fit. It conflicts with the private database design and would require public exposure, IP allowlists with changing runner IPs, VPN, bastion, or a self-hosted runner.
- **SSH/IAP tunnel from GitHub Actions to the VM:** workable but brittle. It adds Compute/IAP/SSH IAM and network complexity to every deploy. Keep it as an emergency/manual operations path, not the default pipeline.
- **Cloud Run Job / GCP-side migration step:** best default. It reuses GCP identity, Secret Manager, private networking, and the backend runtime environment.
- **Manual migrations only:** acceptable for early MVP or high-risk migrations, especially behind `workflow_dispatch` plus environment approval. It should not be the only path once F-02 becomes a foundation for later slices.

### Migration Guardrails

- Use a real migration history table (`alembic_version` or equivalent), never ad hoc "run every SQL file" scripts.
- Make migrations backward-compatible where possible: expand first, deploy code that tolerates both shapes, then contract later.
- Treat the `events` table as higher-risk than projections. The event log is the source of truth; migrations should not rewrite or delete event rows casually.
- Projection tables (`users`, `adrs`) can be rebuilt conceptually, but still need normal backup/restore discipline in production.
- Verify or trigger an on-demand `pg_dump` before destructive or long-running migrations; daily backup alone is not enough for risky schema changes.
- Add down migrations where realistic, but plan rollbacks primarily through compatible schema evolution because Cloud Run revision rollback does not roll back the database.
- Keep the runner single and lock-protected. Use GitHub Actions `concurrency`, one Cloud Run Job task, and optionally a Postgres advisory lock around migration execution.
- Align Postgres compatibility: devcontainer uses Postgres 16 while the GCE VM uses Postgres 15, so migration SQL should avoid PG16-only features unless prod is upgraded.

### Implementation Implications for `/plan persistence-scaffold`

- Add backend dependencies for the chosen migration stack, respecting the backend `exclude-newer = "7 days"` release-age policy.
- Add an initial migration that creates `events`, `users`, and `adrs` according to F-02 and this research's aggregate/schema notes.
- Add local commands, likely a `just backend-migrate` or `just migrate-backend`, that runs from `backend/` with `DATABASE_URL`.
- Add CI that starts an ephemeral Postgres service and runs migrations on a fresh database.
- Add a deploy migration step that executes in GCP, not from the public GitHub runner directly.
- Document the manual break-glass path for running the migration job and checking its logs.

### Code References

- `context/changes/github-issues/F-02-persistence-scaffold.md` - F-02 requires Postgres driver and migration tooling, fresh/existing DB migration success, and `User`/`ADR` schema contract.
- `context/foundation/application-architecture.md` - migrations belong in `infrastructure/`; F-02 delivers `events`, projection tables, port definitions, bootstrap skeleton, and empty dispatcher.
- `context/foundation/infrastructure.md` - GCP platform decision, self-hosted Postgres, and warning that schema migrations do not roll back with Cloud Run revisions.
- `.github/workflows/deploy-gcp.yml` - current deploy workflow; no migration job or DB test workflow.
- `deploy/gcp/run-api.flags` - Cloud Run API settings to mirror for a migration job: VPC egress and Secret Manager `DATABASE_URL`.
- `deploy/gcp/03-gce-postgres.sh` and `deploy/gcp/postgres-vm-setup.sh` - production self-hosted Postgres provisioning.
- `.devcontainer/docker-compose.yml` and `.devcontainer/devcontainer.json` - local Postgres and local `DATABASE_URL`.
- `backend/pyproject.toml` - current backend dependency baseline; no persistence dependencies yet.

### Open Questions

1. **Should production migrations be automatic on every `main` deploy or manually approved through a GitHub Environment?** Recommendation: automatic for additive F-02-style schema creation, approval-gated for destructive or long-running migrations.
2. **Should the migration runner be a committed Cloud Run Job resource or created/updated ad hoc in the workflow?** Recommendation: define/update a stable `adr-flow-api-migrate` job so logs, IAM, and operations are predictable.
3. **Should prod Postgres be upgraded to match dev Postgres 16 before migrations land?** Not required for F-02 if SQL is PG15-compatible, but version alignment lowers future migration risk.
4. **Alembic vs plain SQL migrations:** recommendation is Alembic unless `/plan persistence-scaffold` deliberately chooses a simpler SQL-only runner.
