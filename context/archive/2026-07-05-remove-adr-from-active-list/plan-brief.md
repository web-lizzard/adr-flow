# Remove ADR From Active List — Plan Brief

> Full plan: `context/changes/remove-adr-from-active-list/plan.md`
> Research: `context/changes/remove-adr-from-active-list/research.md`

## What & Why

Users need to remove ADRs from their active workspace card list without permanently destroying records (FR-015). Soft-delete hides the ADR from list, search, get-by-id, and title-uniqueness checks while retaining the event stream and database row for data retention.

## Starting Point

S-03 delivered the read path: `is_deleted` column, repository filters, and `GET /api/adrs` card list. Domain replay for `ADRSoftDeleted` was scaffolded in F-02 but the write path (command, projection, API, UI) was deferred. No schema migration is needed.

## Desired End State

A user clicks a trash icon on any card, confirms in a dialog, and the card disappears. The ADR stays in the DB with `is_deleted = true` and unchanged lifecycle `status`. Deep links to removed ADRs show the existing generic 404. Re-delete returns 400 `adr_already_deleted`. No mutator can change a soft-deleted ADR.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| API route | `DELETE /api/adrs/{id}` → 204 | REST semantics for removal; handler still event-sourced | Plan |
| Re-delete | 400 `adr_already_deleted` | Handler loads from event store where deleted state is visible | Plan |
| Mutator guards | All seven command methods | Prevents appending events after soft-delete on replayed aggregate | Plan |
| Editor deep-link | Generic 404 | No extra frontend work; server already filters deleted rows | Plan |
| Card affordance | Trash icon (`@click.stop`) | Clear destructive action without overflow menu complexity | Plan |
| Confirmation | AlertDialog | Destructive action warrants explicit confirm; no existing pattern in app | Plan |
| List refresh | `fetchList()` after success | Matches current store design; lowest risk | Research |
| Status on delete | Unchanged | Soft-delete orthogonal to lifecycle per F-02 design | Research |

## Scope

**In scope:**

- Domain `soft_delete()`, `AdrAlreadyDeleted`, mutator guards
- `SoftDeleteAdrCommand` handler + `mark_soft_deleted` projection
- `DELETE /api/adrs/{id}` API + integration tests
- Trash icon, AlertDialog, store `remove()`, list refresh
- Domain, command, API, and frontend tests

**Out of scope:**

- Permanent deletion, undelete/restore UX
- Custom "removed" editor page
- List/search query changes (already correct)
- Schema migration

## Architecture / Approach

Event-sourced write mirroring `publish_adr`: lock aggregate → rehydrate from stream → `soft_delete()` → append `ADRSoftDeleted` → `UPDATE adrs SET is_deleted=true` in same UoW → `mark_processed`. Frontend adds `deleteAdr` client call and card-level remove with confirmation; workspace refreshes list on success. Read path unchanged.

```
Card trash → AlertDialog confirm → DELETE /api/adrs/{id}
  → SoftDeleteAdrCommandHandler → ADRSoftDeleted event
  → adrs.is_deleted = true → GET /api/adrs excludes row
```

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Domain layer | `soft_delete()`, guards, `AdrAlreadyDeleted`, domain tests | `_with_soft_deleted` must also set `updated_at` for replay consistency |
| 2. Backend write path & API | Command, projection, `DELETE` route, integration tests | Route ordering / OpenAPI registration with existing `/{adr_id}` routes |
| 3. Frontend remove UX | AlertDialog scaffold, card trash, store wiring, tests | Card is fully clickable today — must `@click.stop` on remove control |

**Prerequisites:** S-03 (`adr-history-cards`) complete; dev environment with `just dev`.

**Estimated effort:** ~2–3 focused sessions across 3 phases; medium vertical slice, established patterns.

## Open Risks & Assumptions

- AlertDialog must be scaffolded (shadcn-vue not yet in repo) — first confirmation-dialog pattern in the app.
- `DELETE` route must not conflict with future resource-level DELETE semantics; MVP only supports soft-delete.
- Async review workers targeting a concurrently deleted ADR will hit `AdrAlreadyDeleted` at domain layer — acceptable edge case.

## Success Criteria (Summary)

- User removes an ADR from workspace cards; it no longer appears in list or search.
- Removed ADR retains data (`is_deleted=true`, status unchanged); title becomes reusable.
- Re-delete and post-delete mutations return typed 400 errors; editor deep-link returns generic 404.
