---
date: 2026-07-05T03:16:00+02:00
researcher: Composer
git_commit: 29bb10bad5669d725369537e721bd7327d5982fc
branch: main
repository: adr-flow
topic: "S-06 remove-adr-from-active-list — soft-delete ADR from active card view (FR-015)"
tags: [research, codebase, adr, soft-delete, s-06, fr-015, history-cards]
status: complete
last_updated: 2026-07-05
last_updated_by: Composer
---

# Research: S-06 Remove ADR From Active List

**Date**: 2026-07-05T03:16:00+02:00
**Researcher**: Composer
**Git Commit**: `29bb10bad5669d725369537e721bd7327d5982fc`
**Branch**: main
**Repository**: adr-flow

## Research Question

What exists in the codebase today for roadmap slice **S-06** (`remove-adr-from-active-list`): letting a user remove their own ADR from the active card view while retaining the record (soft-delete per **FR-015**)?

## Summary

S-06 is **ready to plan** — prerequisite S-03 (`adr-history-cards`) is done. The **read path is complete**: `adrs.is_deleted` exists in schema, all repository queries filter `is_deleted = false`, and the workspace card list already consumes `GET /api/adrs`. The **write path is missing**: no public `soft_delete()` on the aggregate, no `commands/soft_delete_adr.py`, no projection `mark_soft_deleted`, no API route, and no frontend remove action. Domain vocabulary (`ADRSoftDeleted` event, aggregate replay via `_with_soft_deleted()`) was scaffolded in F-02 and deferred from `command-handlers-aggregate-source-of-truth`.

Implementing S-06 is a **vertical slice** across domain → command → projection → API → UI, following the same patterns as `publish_adr` (event append + synchronous projection update in one UoW transaction). No schema migration is expected.

## Detailed Findings

### Product requirements (FR-015)

From `context/foundation/prd.md`:

- **FR-015**: User can remove their own ADR from their active list. A removed ADR no longer appears in the user's card view; in MVP the user cannot permanently destroy the record. Priority: must-have.
- **NFR: Data retention**: ADRs stored indefinitely until consciously removed from active list; removal hides the ADR — permanent destruction is out of scope.
- **Functional non-goal**: No permanent ADR destruction; no restore/undelete in MVP.
- **Functional non-goal**: No filtering or search in the ADR list (card view only).

Roadmap S-06 outcome (`context/foundation/roadmap.md:159-163`): user can remove an ADR from the active card view while the record remains retained (soft-delete). Prerequisites: S-03 (done).

### Database and schema (F-02 — done)

| Artifact | Location | Notes |
|----------|----------|-------|
| `is_deleted` column | [001_initial migration](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/migrations/versions/001_initial_events_users_adrs.py#L69-L74) | `BOOLEAN NOT NULL`, `server_default=false` |
| Partial unique index | [002 migration](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/migrations/versions/002_adrs_active_title_unique_index.py#L21-L28) | `uq_adrs_active_user_title_ci` where `is_deleted = false` — allows title reuse after soft-delete |
| ORM model | [models.py:57-59, 73-79](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/models.py#L57-L79) | Same column + index on `Adr` |

No later migrations touch `is_deleted`. S-03 archive explicitly states S-06 exercises deletion **without schema changes**.

### Domain layer (partial — replay done, command missing)

| Piece | Status | Reference |
|-------|--------|-----------|
| `ADR.is_deleted` field | Done | [aggregate.py:52](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/domain/adr/aggregate.py#L52) |
| `ADRSoftDeleted` event | Done | [events.py:59-60](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/domain/adr/events.py#L59-L60) |
| `restore()` replay | Done | [aggregate.py:142-146](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/domain/adr/aggregate.py#L142-L146) — sets `is_deleted=True`, **status unchanged** |
| `_with_soft_deleted()` | Done (private) | [aggregate.py:242-243](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/domain/adr/aggregate.py#L242-L243) |
| Public `soft_delete()` command method | **Missing** | No method like `publish()` / `submit_for_review()` |
| Guards on other commands for deleted ADRs | **Missing** | Flagged in archived impl-review; not yet implemented |
| Typed error for already-deleted / invalid delete | **Missing** | No `AdrAlreadyDeleted` or similar in [errors.py](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/domain/errors.py) |

**Prior decision (persistence-scaffold research)**: soft-delete is **orthogonal to status** — allowed from any lifecycle status; only `is_deleted` flips; `user_id`, `status`, content, and review fields are retained.

Domain tests already cover replay:
- `test_restore_soft_deleted_sets_is_deleted` — [test_adr_aggregate.py:251-270](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/tests/domain/test_adr_aggregate.py#L251-L270)
- `test_rehydrate_adr_maps_soft_deleted` — [test_adr_rehydrate.py:166-183](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/tests/domain/test_adr_rehydrate.py#L166-L183)

### Application layer (write path missing)

**Existing commands** (`backend/application/commands/`): `create_adr`, `update_adr_content`, `submit_adr_for_review`, `publish_adr`, `retry_adr_for_review`, `register_user`. No `soft_delete_adr.py`.

Architecture doc names the planned command: [application-architecture.md:189](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/context/foundation/application-architecture.md#L189) — `commands/soft_delete_adr.py` (emits `ADRSoftDeleted`).

**Pattern to follow** — `PublishAdrCommandHandler` ([publish_adr.py](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/application/commands/publish_adr.py)):
1. Begin UoW, `lock_aggregate(adr_id)`
2. `load_stream` + `rehydrate_adr`
3. Ownership check → `AdrNotFound` if missing/wrong owner
4. Call aggregate command method
5. `event_store.append` with `aggregate_type="adr"`
6. Synchronous projection update in same transaction
7. `mark_processed` on stored event

**Projection port** ([adr_projection.py](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/application/ports/adr_projection.py)): has `insert`, `update_content`, `mark_in_review`, `mark_proposed`, `apply_review_result`, `record_review_failure`. **No `mark_soft_deleted`.**

**SqlAdrProjection** ([adr_projection.py](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/projections/adr_projection.py)): `insert()` maps `is_deleted` on create (line 114); no `UPDATE … SET is_deleted = true` method.

**Event store**: `ADRSoftDeleted` is registered in `_EVENT_TYPES` ([event_store.py:31](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/event_store.py#L31)) but **not** in `SYNC_PROJECTION_EVENT_TYPES` (lines 36-42). Command handlers apply projection updates directly (like `publish_adr` → `mark_proposed`), so adding to `SYNC_PROJECTION_EVENT_TYPES` is likely unnecessary unless async replay is introduced.

### Read path (done — S-03)

All `SqlAdrRepository` queries filter `Adr.is_deleted.is_(False)`:

| Method | Line | Used by |
|--------|------|---------|
| `find_by_id_for_owner` | [adr_repository.py:27](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/adapters/persistence/repositories/adr_repository.py#L27) | `GET /api/adrs/{id}`, editor |
| `find_by_title_for_owner` | line 43 | Title uniqueness on create |
| `search_by_title` | line 56 | `GET /api/adrs/search` |
| `list_for_owner` | line 75 | `GET /api/adrs` (card list) |

`list_for_owner` returns all non-deleted statuses, sorted `updated_at DESC, id DESC`. No status filter.

Integration tests manually set `is_deleted = true` via SQL and assert exclusion: [test_adr_repository.py:425-482](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/tests/infrastructure/adapters/persistence/test_adr_repository.py#L425-L482).

`AdrSummary` API schema exposes `id`, `title`, `status`, `updated_at` only — `is_deleted` is internal ([schemas/adr.py:95-99](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/api/schemas/adr.py#L95-L99)).

### API layer (list done, delete missing)

| Endpoint | Status | Reference |
|----------|--------|-----------|
| `GET /api/adrs` | Done | [adr.py:151-161](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/backend/infrastructure/api/routers/adr.py#L151-L161) |
| `GET /api/adrs/{id}` | Done — returns 404 for soft-deleted (via repo filter) | lines 174-181 |
| `POST /api/adrs/{id}/publish` | Pattern reference for action route | lines 107-115 |
| `DELETE` or remove action | **Missing** | — |

Existing routes use `get_current_user_id` (session cookie JWT). S-08 (Bearer token) is parallel and does not block S-06 planning, but implementers should follow whichever auth transport is current at implementation time.

### Frontend (list done, remove UI missing)

| Layer | File | Role |
|-------|------|------|
| Workspace page | [workspace/index.vue](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/frontend/app/pages/workspace/index.vue) | Loads cards via `fetchList()` on mount; renders `AdrCard` grid |
| Card component | [AdrCard.vue](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/frontend/app/components/adr/AdrCard.vue) | Title, status badge, last-edited; click navigates to editor — **no remove action** |
| Store | [adr.ts](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/frontend/app/stores/adr.ts) | `fetchList()` → `listAdrs()` |
| API client | [useApi.ts](https://github.com/web-lizzard/adr-flow/blob/29bb10bad5669d725369537e721bd7327d5982fc/frontend/composables/useApi.ts) | `listAdrs()` only; no delete/remove method |

After removal, the list should refresh (optimistic removal or `fetchList()`). Editor deep-link to a removed ADR should surface 404 — already handled server-side once `is_deleted = true`.

## Code References

- `backend/domain/adr/events.py:59-60` — `ADRSoftDeleted` event definition
- `backend/domain/adr/aggregate.py:52,142-146,242-243` — `is_deleted` field, replay, private transition
- `backend/domain/errors.py:42-74` — existing ADR errors (no delete-specific error yet)
- `backend/application/commands/publish_adr.py` — command handler pattern to mirror
- `backend/application/ports/adr_projection.py:10-33` — projection port (missing soft-delete method)
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py` — SQL projection adapter
- `backend/infrastructure/adapters/persistence/repositories/adr_repository.py:27,43,56,75` — read-side `is_deleted` filters
- `backend/infrastructure/api/routers/adr.py:151-161` — list endpoint
- `frontend/app/components/adr/AdrCard.vue` — card UI (remove action gap)
- `frontend/app/pages/workspace/index.vue` — workspace card grid
- `context/foundation/application-architecture.md:118,189` — event vocabulary + planned command name

## Architecture Insights

1. **Event-sourced writes, projection reads**: Soft-delete must emit `ADRSoftDeleted` and update `adrs.is_deleted` in the same UoW transaction — never a direct SQL flag flip from the router.
2. **Read path already correct**: No list-query changes needed; implementing the write path immediately hides removed ADRs from cards, search, get-by-id, and title-uniqueness checks.
3. **Title reuse**: Partial unique index on `(user_id, lower(title)) WHERE is_deleted = false` means a soft-deleted ADR's title becomes available for a new ADR.
4. **Orthogonal lifecycle**: Soft-delete does not change `status`; a `proposed` ADR removed from the list remains `proposed` in the DB.
5. **Lessons to apply during implementation**:
   - Define typed domain errors (e.g. `AdrAlreadyDeleted`) — never bare `DomainError` ([lessons.md](context/foundation/lessons.md)).
   - Keep `soft_delete()` public; `_with_soft_deleted()` private ([lessons.md](context/foundation/lessons.md)).
   - Use `aggregate_type="adr"` (lowercase) in event store ([lessons.md](context/foundation/lessons.md)).

## Historical Context (from prior changes)

| Source | Key decisions |
|--------|---------------|
| `context/archive/2026-06-14-persistence-scaffold/research.md` | `SoftDeleteAdr` → `ADRSoftDeleted`; valid from any status; flip flag only; maps to FR-015 |
| `context/archive/2026-06-14-persistence-scaffold/plan.md` | Schema includes `is_deleted`; manual verification: ownership/status retained on soft-delete |
| `context/archive/2026-06-16-adr-history-cards/plan.md` | Soft-delete explicitly out of S-03 scope; `list_for_owner` filters `is_deleted=false`; no migration for S-06 |
| `context/archive/2026-06-18-command-handlers-aggregate-source-of-truth/plan.md` | `ADRSoftDeleted` handler deferred; `_with_soft_deleted()` prepared |
| `context/archive/2026-06-18-command-handlers-aggregate-source-of-truth/reviews/impl-review-phase-1.md` | Command methods don't reject ops on soft-deleted ADRs — fix skipped, relevant for S-06 |
| `context/changes/roadmap-github-issues-proposal.md:525-555` | S-06 definition of done; direct-link behavior **TBD in plan** |

## Related Research

- `context/archive/2026-06-14-persistence-scaffold/research.md` — original soft-delete domain model
- `context/archive/2026-06-16-adr-history-cards/plan.md` — list API and read-path contracts
- `context/changes/roadmap-github-issues-proposal.md` — GitHub issue body draft for S-06

## Open Questions

These are intentionally left for `/plan` — not blockers for planning:

1. **Direct-link behavior**: If a user bookmarks `/workspace/adr/{id}` and the ADR is removed, `GET /api/adrs/{id}` already returns 404 via repo filter. Should the editor page show a specific "removed" message vs generic not-found? (Issue proposal marks this TBD.)
2. **Idempotent delete**: Should `DELETE` on an already-soft-deleted ADR return 204 (idempotent) or 404? Repo returns `None` for deleted rows, so re-delete looks like `AdrNotFound` unless the handler checks `is_deleted` before the filter.
3. **Guards on other commands**: Should `update_content`, `publish`, `submit_for_review`, etc. reject when `is_deleted=True`? Archived impl-review flagged this; aggregate currently has no such guards.
4. **HTTP verb**: `DELETE /api/adrs/{id}` vs `POST /api/adrs/{id}/remove` — follow `publish` sub-resource pattern or REST delete?
5. **UI affordance**: Icon button on card vs overflow menu vs confirmation dialog — product/UX decision for plan.
6. **Confirmation step**: Should removal require explicit confirmation (recommended for irreversible-from-user-perspective action, even though data is retained)?

## Suggested implementation surface (for `/plan`)

| Layer | Deliverable |
|-------|-------------|
| Domain | `soft_delete()` public method; `AdrAlreadyDeleted` (or idempotent no-op); optional guards on other commands |
| Application | `SoftDeleteAdrCommand` + handler; `AdrProjection.mark_soft_deleted` |
| Infrastructure | `SqlAdrProjection.mark_soft_deleted`; API route; DI wiring in `bootstrap.py` / `dependencies.py` |
| Frontend | Remove action on card; API client method; store action + list refresh |
| Tests | Domain aggregate tests; command handler test; API integration test; frontend store/component test |

**Estimated scope**: Medium vertical slice — ~6-8 files backend, ~3-4 frontend, no migration. Follows established patterns; main design work is UX and edge-case policy (open questions above).
