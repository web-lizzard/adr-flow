# Remove ADR From Active List — Implementation Plan

## Overview

Implement roadmap slice **S-06** (FR-015): let a user remove their own ADR from the workspace card list via soft-delete. The record stays in the database and event store; read paths already filter `is_deleted = false`. This plan adds the event-sourced write path (`ADRSoftDeleted` → projection) and a card-level remove UX with confirmation.

## Current State Analysis

The read path is complete from S-03 (`adr-history-cards`):

- `adrs.is_deleted` column and partial unique title index exist (F-02).
- `SqlAdrRepository` filters `is_deleted = false` on all queries.
- `GET /api/adrs` drives the workspace card grid; soft-deleted ADRs are already excluded when the flag is set.

The write path is missing:

- No public `ADR.soft_delete()` command method (only private `_with_soft_deleted()` and replay).
- No `SoftDeleteAdrCommand` handler or `AdrProjection.mark_soft_deleted`.
- No `DELETE /api/adrs/{id}` route.
- No frontend remove action or API client method.
- No `is_deleted` guards on other aggregate command methods (flagged in archived impl-review).

### Key Discoveries:

- `ADRSoftDeleted` event and replay scaffolding exist in `backend/domain/adr/aggregate.py` — deferred from F-02 command-handlers work.
- `publish_adr` is the canonical handler pattern: UoW lock → load stream → rehydrate → ownership check → aggregate command → append event → sync projection → `mark_processed`.
- Handler loads from the **event store**, not the read projection — so re-delete on an already-soft-deleted ADR surfaces as `AdrAlreadyDeleted` (400), not `AdrNotFound`.
- `_with_soft_deleted()` does not set `updated_at` today; other `_with_*` helpers do — fix required for list sort consistency.
- Frontend has no confirmation-dialog primitive yet; `reka-ui` / shadcn-vue are configured but `AlertDialog` is not scaffolded.

## Desired End State

A signed-in user can click a trash icon on any ADR card, confirm removal in a dialog, and the card disappears from the workspace list. The ADR remains in the database with `is_deleted = true` and unchanged `status`. Deep-linking to a removed ADR's editor shows the existing generic not-found experience (404 from `GET /api/adrs/{id}`). Re-attempting removal returns 400 `adr_already_deleted`. No other command can mutate a soft-deleted ADR.

### Verification

- `DELETE /api/adrs/{id}` returns 204 for owner; 404 for missing/wrong owner; 401 unauthenticated; 400 for already deleted.
- Workspace card grid no longer shows the removed ADR after success.
- Domain tests cover `soft_delete()` from every status and guard rejection on all mutators.
- No schema migration required.

## What We're NOT Doing

- Permanent ADR destruction or undelete/restore UX (PRD non-goals).
- Changes to list/search/get query filters (already correct).
- Custom "removed from your list" editor page — generic 404 only.
- Async projection replay wiring (`SYNC_PROJECTION_EVENT_TYPES`).
- Filtering or search in the card view.

## Implementation Approach

Three incremental phases: domain invariants first, then backend write path + API, then frontend UX. Each phase is independently testable. The write path follows `publish_adr` conventions (event append + synchronous projection in one UoW transaction, `aggregate_type="adr"`, typed domain errors per `lessons.md`).

**Planning decisions (from `/plan` session):**

| Decision | Choice |
|----------|--------|
| API route | `DELETE /api/adrs/{id}` → 204 |
| Re-delete | 400 `adr_already_deleted` |
| Mutator guards | All seven command methods reject when `is_deleted=True` |
| Editor deep-link | Generic 404 (no custom message) |
| Card affordance | Trash icon button (corner, `@click.stop`) |
| Confirmation | AlertDialog before remove |

## Phase 1: Domain Layer

### Overview

Add the public soft-delete command surface, typed error, `is_deleted` guards on all mutators, and fix `_with_soft_deleted` to update `updated_at`. Domain tests prove invariants before wiring infrastructure.

### Changes Required:

#### 1. Domain error

**File**: `backend/domain/errors.py`

**Intent**: Add a typed error for soft-delete and mutator-guard rejections so API and tests match stable `kind` values, not string messages.

**Contract**: New `AdrAlreadyDeleted(DomainError)` with default message `"ADR has already been removed from the active list"`; `kind` resolves to `adr_already_deleted`.

#### 2. Aggregate command method and guards

**File**: `backend/domain/adr/aggregate.py`

**Intent**: Expose `soft_delete(updated_at)` as the sole entry point for marking an ADR removed; block all other mutations on deleted aggregates.

**Contract**:

- Private `_ensure_not_deleted()` raises `AdrAlreadyDeleted` when `self.is_deleted`.
- Call `_ensure_not_deleted()` at the top of: `update_content`, `update_title`, `submit_for_review`, `retry_review`, `publish`, `complete_review`, `fail_review`.
- Public `soft_delete(updated_at: datetime) -> Self`: if `is_deleted`, raise `AdrAlreadyDeleted`; else return `_with_soft_deleted(updated_at)`.
- `_with_soft_deleted(updated_at: datetime)`: `replace(self, is_deleted=True, updated_at=updated_at)`.
- `restore()` `ADRSoftDeleted` case: pass `event.occurred_at` to `_with_soft_deleted`.

#### 3. Domain exports

**File**: `backend/domain/adr/__init__.py`

**Intent**: Export `AdrAlreadyDeleted` if other packages import ADR errors from the package root (match existing export pattern).

**Contract**: Re-export `AdrAlreadyDeleted` from `domain.errors` if sibling errors are exported there.

#### 4. Domain tests

**File**: `backend/tests/domain/test_adr_aggregate.py`

**Intent**: Lock in soft-delete behavior and guard coverage.

**Contract**: New tests for:

- `soft_delete()` sets `is_deleted=True`, preserves `status`, content, review fields, `user_id`.
- `soft_delete()` from each `AdrStatus` value (parametrize).
- `soft_delete()` updates `updated_at`.
- Second `soft_delete()` on same aggregate → `AdrAlreadyDeleted`.
- Each mutating command on an aggregate with `is_deleted=True` (via replay stream ending in `ADRSoftDeleted`) → `AdrAlreadyDeleted`.

**File**: `backend/tests/domain/test_adr_errors.py` (if present) or extend existing error tests

**Intent**: Assert `AdrAlreadyDeleted.kind == "adr_already_deleted"`.

**Contract**: One test for error kind and default message.

### Success Criteria:

#### Automated Verification:

- Domain tests pass: `cd backend && uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_adr_errors.py -q`
- Ruff passes: `cd backend && uv run ruff check domain/ tests/domain/`
- Type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- Review aggregate: every public mutator except `soft_delete` calls `_ensure_not_deleted()` before status checks.
- Replay path still sets `is_deleted` and preserves `status` after `_with_soft_deleted(updated_at)` change.

**Implementation Note**: Pause after automated verification passes and confirm manual review before Phase 2.

---

## Phase 2: Backend Write Path & API

### Overview

Wire `SoftDeleteAdrCommand` through projection and expose `DELETE /api/adrs/{id}`. Mirror `publish_adr` handler flow; projection sets `is_deleted = true` without changing `status`.

### Changes Required:

#### 1. Projection port

**File**: `backend/application/ports/adr_projection.py`

**Intent**: Declare the soft-delete projection write operation.

**Contract**: `async def mark_soft_deleted(self, adr_id: UUID, *, updated_at: datetime) -> bool: ...`

#### 2. SQL projection adapter

**File**: `backend/infrastructure/adapters/persistence/projections/adr_projection.py`

**Intent**: Update the read model row when `ADRSoftDeleted` is processed.

**Contract**: `mark_soft_deleted` executes `UPDATE adrs SET is_deleted = true, updated_at = :updated_at WHERE id = :adr_id AND is_deleted = false`; returns `rowcount == 1` (defense-in-depth vs race, same pattern as `mark_proposed`).

#### 3. Command handler

**File**: `backend/application/commands/soft_delete_adr.py` (new)

**Intent**: Orchestrate soft-delete as an event-sourced write in one UoW transaction.

**Contract**:

- `SoftDeleteAdrCommand(adr_id: UUID, user_id: UUID)` frozen dataclass.
- Handler flow mirrors `PublishAdrCommandHandler`: lock → load stream `"adr"` → rehydrate → ownership check (`AdrNotFound`) → `adr.soft_delete(updated_at)` → append `ADRSoftDeleted` → `mark_soft_deleted` → if not transitioned raise `AdrAlreadyDeleted` → `mark_processed` → structured logging (`command.soft_delete_adr.*`).

#### 4. Test fakes

**File**: `backend/tests/application/commands/fakes.py`

**Intent**: Support command handler unit tests.

**Contract**: `FakeAdrProjection.mark_soft_deleted(adr_id, *, updated_at) -> bool` appends to `marked_soft_deleted: list` and returns `True` by default.

#### 5. Command handler tests

**File**: `backend/tests/application/commands/test_soft_delete_adr.py` (new)

**Intent**: Verify handler orchestration without database.

**Contract**: Tests mirror `test_publish_adr.py`:

- Happy path: emits `ADRSoftDeleted`, calls `mark_soft_deleted`, `mark_processed`.
- Empty stream / wrong owner → `AdrNotFound`.
- Stream ending in `ADRSoftDeleted` → `AdrAlreadyDeleted`.

#### 6. API route and DI

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Expose soft-delete to authenticated owners.

**Contract**: `DELETE /{adr_id}` with `status_code=204`, `Depends(get_current_user_id)`, `Depends(get_soft_delete_adr_handler)`; log `route.adrs.delete.completed`.

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Resolve handler from app state.

**Contract**: `get_soft_delete_adr_handler(request) -> SoftDeleteAdrCommandHandler`.

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Construct and register handler at startup.

**Contract**: `SoftDeleteAdrCommandHandler(uow_factory)` → `app.state.soft_delete_adr_handler`.

#### 7. API integration tests

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: End-to-end HTTP contract for soft-delete.

**Contract**: New tests:

- `DELETE /api/adrs/{id}` → 204; subsequent `GET /api/adrs` omits the ADR; `GET /api/adrs/{id}` → 404.
- Second `DELETE` on same id → 400, `kind == "adr_already_deleted"`.
- Missing ADR / wrong owner → 404 `adr_not_found`.
- Unauthenticated → 401.
- Assert `is_deleted = true` and `status` unchanged in DB (optional SQL assertion, matching publish test style).

#### 8. Projection adapter test (if coverage file exists)

**File**: `backend/tests/infrastructure/adapters/persistence/test_adr_projection*.py`

**Intent**: Verify SQL `mark_soft_deleted` rowcount behavior (success vs already deleted).

**Contract**: `mark_soft_deleted` returns `True` once, `False` on second call for same row.

### Success Criteria:

#### Automated Verification:

- Command tests pass: `cd backend && uv run pytest tests/application/commands/test_soft_delete_adr.py -q`
- API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k delete -q`
- Full backend suite passes: `cd backend && uv run pytest -q`
- Ruff and ty pass on touched backend files

#### Manual Verification:

- `curl -X DELETE` (with session cookie) removes ADR from list response.
- OpenAPI docs show `DELETE /api/adrs/{adr_id}` returning 204.

**Implementation Note**: Pause after automated verification; manually confirm curl/list behavior before Phase 3.

---

## Phase 3: Frontend Remove UX

### Overview

Add trash icon + confirmation dialog on each card, wire `deleteAdr` API call through the store, refresh the list on success.

### Changes Required:

#### 1. AlertDialog UI primitive

**File**: `frontend/app/components/ui/alert-dialog/` (new, via shadcn-vue pattern)

**Intent**: Provide accessible confirmation dialog for destructive remove action.

**Contract**: Scaffold AlertDialog components (`AlertDialog`, `AlertDialogTrigger`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogCancel`, `AlertDialogAction`) consistent with existing `button`/`card` shadcn setup in `components.json`.

#### 2. API client

**File**: `frontend/composables/useApi.ts`

**Intent**: Call backend soft-delete endpoint.

**Contract**: `deleteAdr(id: string)` → `$fetch<void>(apiPath(\`/adrs/${id}\`), { method: "DELETE" })`.

#### 3. Store action

**File**: `frontend/app/stores/adr.ts`

**Intent**: Encapsulate remove mutation and list refresh.

**Contract**: `remove(id: string): Promise<void>` — set `loading`, call `deleteAdr(id)`, then `await fetchList()`; on failure leave list unchanged and rethrow for UI error handling.

**File**: `frontend/app/composables/useAdr.ts`

**Intent**: Expose `remove` to pages/components.

**Contract**: Pass through `store.remove`.

#### 4. AdrCard remove affordance

**File**: `frontend/app/components/adr/AdrCard.vue`

**Intent**: Let user initiate remove from the card without navigating to the editor.

**Contract**:

- Trash icon `Button` (`variant="ghost"`, `size="icon"`) in card header corner with `aria-label="Remove ADR"`.
- `@click.stop` on remove control so card navigation does not fire.
- Wrap in AlertDialog: title "Remove ADR?", description names the card title; Cancel / Remove (destructive) actions.
- On confirm: emit `remove` event with `id` prop (parent owns store call) **or** accept optional `@remove` callback prop — prefer emit for testability.
- Disable remove button while removal in flight (prop `removing?: boolean`).

#### 5. Workspace page wiring

**File**: `frontend/app/pages/workspace/index.vue`

**Intent**: Handle remove from card grid and surface errors.

**Contract**:

- Listen `@remove` on `AdrCard`; call `adr.remove(id)`.
- Track per-card or global removing state; show inline error or toast on failure via `getAuthErrorMessage` (match editor publish pattern).
- Optional success toast: "ADR removed from your list" (via `vue-sonner`, consistent with publish feedback).

#### 6. Frontend tests

**File**: `frontend/tests/adr-card.test.ts`

**Intent**: Verify remove affordance does not break navigation.

**Contract**:

- Trash button present with accessible label.
- Clicking trash does not call `navigateTo`.
- Confirm action emits `remove` with correct id (mock AlertDialog or stub confirm handler).

**File**: `frontend/tests/adr.store.test.ts`

**Intent**: Verify store remove calls API and refreshes list.

**Contract**: Mock `deleteAdr` + `listAdrs`; assert `remove()` triggers both and updates `adrs` after refresh.

### Success Criteria:

#### Automated Verification:

- Frontend tests pass: `cd frontend && pnpm run test -- adr-card adr.store`
- Lint passes: `cd frontend && pnpm run lint`
- Typecheck passes: `cd frontend && pnpm run typecheck`

#### Manual Verification:

- Workspace shows trash icon on each card; clicking opens confirmation dialog.
- Confirm removes card from grid without full page reload.
- Cancel closes dialog; card remains.
- Bookmarked editor URL for removed ADR shows existing generic not-found UI.
- Re-remove via API returns error (not reachable from UI after list refresh).

**Implementation Note**: Pause for manual UX confirmation before marking change complete.

---

## Testing Strategy

### Unit Tests:

- Domain: `soft_delete()` invariants, status preservation, `AdrAlreadyDeleted` on double-delete and guarded mutators.
- Command: handler emits event, updates projection, marks processed; error paths.
- Store: `remove()` calls `deleteAdr` then `fetchList`.

### Integration Tests:

- API: full DELETE flow, list exclusion, get-by-id 404, auth and ownership, re-delete 400.
- Projection SQL: `mark_soft_deleted` idempotency at row level.

### Manual Testing Steps:

1. Create two ADRs; remove one from workspace — only the other remains.
2. Remove a `proposed` ADR — confirm status in DB unchanged, `is_deleted = true`.
3. Create new ADR with same title as removed one — succeeds (partial unique index).
4. Open removed ADR editor URL — generic not-found.
5. Attempt `DELETE` again via API — 400 `adr_already_deleted`.

## Performance Considerations

Negligible — single-row UPDATE by primary key; list refresh reuses existing `GET /api/adrs`. No new indexes or migrations.

## Migration Notes

None. `is_deleted` column and read-path filters already exist from F-02/S-03.

## References

- Research: `context/changes/remove-adr-from-active-list/research.md`
- PRD FR-015: `context/foundation/prd.md`
- Roadmap S-06: `context/foundation/roadmap.md`
- Handler pattern: `backend/application/commands/publish_adr.py`
- Archived soft-delete design: `context/archive/2026-06-14-persistence-scaffold/research.md`
- Lessons: `context/foundation/lessons.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Domain Layer

#### Automated

- [x] 1.1 Domain tests pass: `cd backend && uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_adr_errors.py -q` — 384aca4
- [x] 1.2 Ruff passes: `cd backend && uv run ruff check domain/ tests/domain/` — 384aca4
- [x] 1.3 Type check passes: `cd backend && uv run ty check` — 384aca4

#### Manual

- [x] 1.4 Review aggregate: every public mutator except `soft_delete` calls `_ensure_not_deleted()` before status checks — 384aca4
- [x] 1.5 Replay path still sets `is_deleted` and preserves `status` after `_with_soft_deleted(updated_at)` change — 384aca4

### Phase 2: Backend Write Path & API

#### Automated

- [x] 2.1 Command tests pass: `cd backend && uv run pytest tests/application/commands/test_soft_delete_adr.py -q` — 268a7ef
- [x] 2.2 API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k delete -q` — 268a7ef
- [x] 2.3 Full backend suite passes: `cd backend && uv run pytest -q` — 268a7ef
- [x] 2.4 Ruff and ty pass on touched backend files — 268a7ef

#### Manual

- [x] 2.5 `curl -X DELETE` (with session cookie) removes ADR from list response — 268a7ef
- [x] 2.6 OpenAPI docs show `DELETE /api/adrs/{adr_id}` returning 204 — 268a7ef

### Phase 3: Frontend Remove UX

#### Automated

- [x] 3.1 Frontend tests pass: `cd frontend && pnpm run test -- adr-card adr.store` — 78be033
- [x] 3.2 Lint passes: `cd frontend && pnpm run lint` — 78be033
- [x] 3.3 Typecheck passes: `cd frontend && pnpm run typecheck` — 78be033

#### Manual

- [x] 3.4 Workspace trash icon opens confirmation; confirm removes card from grid — 78be033
- [x] 3.5 Cancel closes dialog without removing; bookmarked editor URL for removed ADR shows generic not-found — 78be033
