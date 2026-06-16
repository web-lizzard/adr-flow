# ADR History Cards Implementation Plan

## Overview

Build S-03: card-based ADR history on the workspace page. Logged-in users browse all owned ADRs (title, status, last-edited), open any card to view or edit per FR-005, and return to the workspace to see updated cards. This is a full-stack vertical slice on top of S-02's create/edit/save foundation — no schema migration required.

## Current State Analysis

**Backend (ready):** S-02 delivered ADR CRUD (`POST`, `GET /{id}`, `PATCH`, beacon `POST /save`), title search (`GET /search?q=`), `AdrSummary` schema (`id`, `title`, `status`, `updated_at`), `AdrReadModel`, `SqlAdrRepository` with owner + `is_deleted` filtering, and integration tests in `test_adr_api.py`. `UpdateAdrContentCommandHandler` blocks edits when `status == in_review`.

**Backend (missing):** No `list_for_owner` on `AdrRepository`, no `ListAdrsQuery` handler, no `GET /api/adrs` list endpoint. Architecture doc (`application-architecture.md`) describes this read path but it was deferred from S-02.

**Frontend (ready):** S-02 delivered `/workspace` (create form), `/workspace/adr/[id]` (editor with CodeMirror + save-on-blur/unload), `useAdrStore`, `useApi.ts` with typed `AdrSummary`, auth middleware, and shadcn `Card` primitives.

**Frontend (missing):** No list fetch in API client or store, no card components, no history section on workspace, no status display, no read-only editor mode for `in_review`, no back navigation from editor.

### Key Discoveries:

- `AdrSummary` already matches card field requirements — reuse for list response (`backend/infrastructure/api/schemas/adr.py:51-55`)
- `GET /api/adrs/search` cannot serve as list-all: requires `q` with `min_length=1` and ILIKE semantics; PRD non-goal forbids search in list UI
- Route ordering in `adr.py`: list route (`GET ""`) and search (`GET /search`) must remain registered before `GET /{adr_id}`
- No `Badge` shadcn component in frontend yet — status badges will be a small dedicated component with Tailwind color classes
- `onMounted` on workspace page fires on every navigation back from editor (Nuxt default, no keep-alive) — sufficient for "refresh on return"

## Desired End State

A logged-in user opens `/workspace` and sees the existing create form plus a "Your ADRs" section below. If they have ADRs, cards display in a responsive grid sorted by last-edited (newest first), each showing title, color-coded status badge, and formatted last-edited timestamp. Clicking a card navigates to `/workspace/adr/{id}`. Opening an ADR in `in_review` shows content read-only with a status banner; all other statuses remain editable per S-02. A "Back to workspace" link on the editor page returns to the card list with fresh data. Empty history shows an inline message pointing to the create form above.

**Verification:** Create several ADRs (or seed via API) → workspace shows cards with correct fields → open draft → edit title → back to workspace → card reflects update → open `in_review` ADR (seeded in test) → editor is read-only → other user's ADRs never appear.

## What We're NOT Doing

- List filtering or search UI (PRD non-goal; search endpoint stays for title-uniqueness validation only)
- Soft-delete / remove from list (S-06)
- Submit for AI review / status transitions (S-04, S-05)
- Persistent sidebar navigation
- E2E browser tests (no Playwright/Cypress infra yet)
- Schema migration or new DB columns
- `created_at` on cards (FR-013 requires last-edited only)

## Implementation Approach

Follow the established S-02 vertical-slice pattern: backend repository + query handler + API route with integration tests, then frontend API client + store extension, then UI components wired into existing workspace and editor pages. Reuse `AdrSummary` DTO and `_to_adr_summary` mapper. Do not repurpose the search endpoint.

## Critical Implementation Details

### Route registration order

Register `GET /api/adrs` (list) on the ADR router before the `/{adr_id}` path parameter route. FastAPI matches in declaration order; a misplaced list route could be swallowed by the ID route.

### Read-only editor for `in_review`

FR-005 permits editing in all statuses except `in_review`. Frontend must disable title input and CodeMirror editing (via `readonly` prop on `AdrMarkdownEditor`) and skip `useAdrPersistence` save triggers when read-only. Backend guard remains as defense-in-depth.

---

## Phase 1: Backend List API

### Overview

Add the list read path: repository method, query handler, HTTP endpoint, DI wiring, and integration tests.

### Changes Required:

#### 1. Repository port extension

**File**: `backend/application/ports/adr_repository.py`

**Intent**: Declare the list contract so query handlers depend on a port, not SQL.

**Contract**: Add `async def list_for_owner(self, user_id: UUID) -> list[AdrReadModel]` to `AdrRepository` protocol. Results ordered by `updated_at` descending; non-deleted ADRs for the given `user_id` only.

#### 2. SQL repository adapter

**File**: `backend/infrastructure/adapters/persistence/repositories/adr_repository.py`

**Intent**: Implement the list query against the existing `adrs` projection table.

**Contract**: `list_for_owner` — `SELECT` where `user_id` matches and `is_deleted = false`, `ORDER BY updated_at DESC`. Map rows via existing `_to_read_model`.

#### 3. List query handler

**File**: `backend/application/queries/list_adrs.py` (new)

**Intent**: Application-layer read handler mirroring `search_adrs_by_title.py`.

**Contract**: `ListAdrsQuery(user_id: UUID)` dataclass; `ListAdrsQueryHandler.handle(query) -> list[AdrReadModel]` delegates to `adr_repository.list_for_owner`.

#### 4. Response schema

**File**: `backend/infrastructure/api/schemas/adr.py`

**Intent**: Typed list response for OpenAPI consumers.

**Contract**: `ListAdrsResponse` with `results: list[AdrSummary]` — parallel to existing `SearchAdrsResponse`.

#### 5. API route

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Expose list endpoint for authenticated users.

**Contract**: `GET ""` (i.e. `/api/adrs`) returning `ListAdrsResponse`, authenticated via `get_current_user_id`, maps results through `_to_adr_summary`. Register before `GET /{adr_id}`.

#### 6. Bootstrap and dependencies

**Files**: `backend/infrastructure/bootstrap.py`, `backend/infrastructure/api/dependencies.py`

**Intent**: Wire handler into composition root and FastAPI DI.

**Contract**: Instantiate `ListAdrsQueryHandler(adr_repository)`; store on `app.state.list_adrs_handler`; add `get_list_adrs_handler` dependency getter.

#### 7. Tests

**Files**: `backend/tests/application/queries/test_list_adrs.py` (new), `backend/tests/infrastructure/api/test_adr_api.py`, `backend/tests/infrastructure/adapters/persistence/test_adr_repository.py`

**Intent**: Lock list behavior at unit, repository, and API layers.

**Contract**: Cover — empty list for new user; multiple ADRs returned sorted by `updated_at` DESC; all four statuses included; soft-deleted ADRs excluded; cross-user isolation; unauthenticated returns 401.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run ruff check .`
- `cd backend && uv run ty check`
- `cd backend && uv run pytest tests/application/queries/test_list_adrs.py tests/infrastructure/api/test_adr_api.py tests/infrastructure/adapters/persistence/test_adr_repository.py -k list`

#### Manual Verification:

- `curl` (or Swagger) `GET /api/adrs` with session cookie returns owned ADRs as `AdrSummary` array
- Creating a second ADR and re-listing shows both, newest-edited first

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Frontend List Plumbing

### Overview

Extend the API client and Pinia store with list fetch capability; wire workspace page to load and refresh the list.

### Changes Required:

#### 1. API client

**File**: `frontend/composables/useApi.ts`

**Intent**: Add typed list fetch alongside existing ADR API helpers.

**Contract**: `ListAdrsResponse` type (`results: AdrSummary[]`); `listAdrs()` → `GET /adrs` via `apiPath`.

#### 2. Store extension

**File**: `frontend/app/stores/adr.ts`

**Intent**: Hold list state and expose `fetchList` action for workspace consumption.

**Contract**: Add `adrs: ref<AdrSummary[]>` (or mapped type with camelCase `updatedAt`), `listLoading: ref<boolean>`, `listError: ref<string | null>`; `fetchList()` calls `listAdrs()`, populates `adrs`, handles loading/error. Existing single-ADR state unchanged.

#### 3. Composable passthrough

**File**: `frontend/app/composables/useAdr.ts`

**Intent**: Expose list state and `fetchList` through the thin composable wrapper (mirrors existing pattern).

**Contract**: Return `adrs`, `listLoading`, `listError`, `fetchList` from store.

#### 4. Workspace fetch lifecycle

**File**: `frontend/app/pages/workspace/index.vue`

**Intent**: Load ADR list when workspace is visited (including return from editor).

**Contract**: Call `fetchList()` in `onMounted`. Display loading skeleton or spinner in history section while `listLoading` is true; show error message if `listError` is set.

#### 5. Store tests

**File**: `frontend/tests/adr.store.test.ts`

**Intent**: Unit-test list fetch behavior.

**Contract**: Mock `listAdrs`; verify `fetchList` populates `adrs`, sets loading flags, handles API error.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run typecheck`
- `cd frontend && pnpm run lint`
- `cd frontend && pnpm run test -- adr.store.test.ts`

#### Manual Verification:

- With backend running and authenticated session, workspace page triggers `GET /api/adrs` (visible in network tab)
- List data available in store (cards not yet rendered — Phase 3)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Card UI & Workspace Integration

### Overview

Build card and status badge components; render the history grid on the workspace page with empty state.

### Changes Required:

#### 1. Status badge component

**File**: `frontend/app/components/adr/AdrStatusBadge.vue` (new)

**Intent**: Human-readable, color-coded status labels per planning decision.

**Contract**: Prop `status: string`. Map `draft` → gray, `in_review` → amber, `after_review` → blue, `proposed` → green. Display labels: "Draft", "In review", "After review", "Proposed". Small pill/badge styling via Tailwind (no new shadcn dependency required).

#### 2. ADR card component

**File**: `frontend/app/components/adr/AdrCard.vue` (new)

**Intent**: Single clickable card showing title, status, and last-edited.

**Contract**: Props: `id`, `title`, `status`, `updatedAt`. Render shadcn `Card` with title, `AdrStatusBadge`, and formatted relative or locale date string. Emit click or use `@click` → `navigateTo(/workspace/adr/${id})`. Entire card is clickable with hover affordance.

#### 3. Workspace history section

**File**: `frontend/app/pages/workspace/index.vue`

**Intent**: Integrate card grid below the existing create form.

**Contract**: Below create `Card`, add "Your ADRs" heading. If `adrs.length === 0` and not loading, show inline empty message: "No ADRs yet — create your first one above." If ADRs exist, render responsive grid (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`) of `AdrCard` components. Create form remains above cards (unchanged position).

#### 4. Component test

**File**: `frontend/tests/adr-card.test.ts` (new)

**Intent**: Verify card renders title, status badge, and formatted date from props.

**Contract**: Mount `AdrCard` with sample props; assert text content and badge label present.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run typecheck`
- `cd frontend && pnpm run lint`
- `cd frontend && pnpm run test -- adr-card.test.ts`

#### Manual Verification:

- Workspace shows card grid with correct title, status badge, and last-edited for each ADR
- Empty state message appears for user with no ADRs
- Clicking a card opens `/workspace/adr/{id}` with correct content
- Cards sorted newest-edited first

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Status-Aware Editor & Navigation

### Overview

Enforce read-only UX for `in_review`, add status display and back navigation on the editor page, and finalize polish.

### Changes Required:

#### 1. Read-only editor support

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`

**Intent**: Allow parent pages to disable editing without swapping components.

**Contract**: Optional prop `readonly?: boolean` (default `false`). When true, pass CodeMirror `readonly` / `editable: false` extension so content is viewable but not editable; suppress blur save emission if appropriate.

#### 2. Editor page status UX

**File**: `frontend/app/pages/workspace/adr/[id].vue`

**Intent**: Respect FR-005 in the UI and improve navigation.

**Contract**:
- Computed `isReadOnly` when `currentAdr.status === 'in_review'`
- When read-only: disable title `Input`, pass `readonly` to `AdrMarkdownEditor`, show banner ("This ADR is being reviewed and cannot be edited."), display `AdrStatusBadge` in header
- Skip or no-op `useAdrPersistence` save triggers when read-only
- Add `NuxtLink` or button "← Back to workspace" linking to `/workspace` above the heading
- For editable statuses: show status badge alongside existing edit UI; update page subtitle to reflect status where helpful

#### 3. Date formatting utility (if needed)

**File**: `frontend/app/utils/formatAdrDate.ts` (new, only if inline formatting is duplicated)

**Intent**: Consistent last-edited display on cards and editor.

**Contract**: `formatAdrDate(iso: string) -> string` using `Intl.DateTimeFormat` or `toLocaleDateString`. Used by `AdrCard` (and editor if showing `updatedAt`).

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run typecheck`
- `cd frontend && pnpm run lint`
- `cd frontend && pnpm run test`
- `just test-backend` (full backend suite, no regressions)

#### Manual Verification:

- Open `in_review` ADR → editor read-only, banner visible, save does not fire on blur
- Open `draft` ADR → fully editable, save-on-blur works as before
- "Back to workspace" returns to card list with updated title/timestamp after edits
- Status badges render correctly on both cards and editor page

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to archive.

---

## Testing Strategy

### Unit Tests:

- `ListAdrsQueryHandler` delegates to repository
- `SqlAdrRepository.list_for_owner` — sort order, deleted filter, owner scope
- `useAdrStore.fetchList` — success, loading, error paths
- `AdrCard` — renders props correctly
- `AdrStatusBadge` — maps all four statuses (can be part of card test or separate)

### Integration Tests:

- `GET /api/adrs` — auth, isolation, sort, all statuses, empty list
- Existing `test_patch_in_review_status_returns_error` remains valid (defense-in-depth)

### Manual Testing Steps:

1. Register/login → create 2+ ADRs with distinct titles
2. Return to workspace → verify cards appear below create form, sorted by last edit
3. Click card → edit title → back to workspace → verify card updated
4. Seed or transition an ADR to `in_review` (direct DB or future S-04) → open → verify read-only
5. Log in as different user → verify first user's ADRs not visible
6. User with zero ADRs → verify empty-state message, no broken layout

## Performance Considerations

MVP scale is small personal history (< 100 ADRs per user per PRD). A single unpaginated `GET /api/adrs` is sufficient. Existing `ix_adrs_user_id` index supports the owner filter. No caching layer needed.

## Migration Notes

None. Uses existing `adrs` table and `AdrSummary` shape. Soft-deleted rows (`is_deleted = true`) are excluded at query level — S-06 will exercise deletion without schema changes.

## References

- PRD: `context/foundation/prd.md` — US-02, FR-013, FR-005
- Roadmap: `context/foundation/roadmap.md` — S-03
- S-02 archive: `context/archive/2026-06-16-draft-authoring-persistence/plan.md`
- Architecture: `context/foundation/application-architecture.md` — list ADRs read example
- Existing schemas: `backend/infrastructure/api/schemas/adr.py`
- Existing workspace: `frontend/app/pages/workspace/index.vue`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Backend List API

#### Automated

- [x] 1.1 `cd backend && uv run ruff check .` — 504af37
- [x] 1.2 `cd backend && uv run ty check` — 504af37
- [x] 1.3 `cd backend && uv run pytest tests/application/queries/test_list_adrs.py tests/infrastructure/api/test_adr_api.py tests/infrastructure/adapters/persistence/test_adr_repository.py -k list` — 504af37

#### Manual

- [ ] 1.4 `GET /api/adrs` returns owned ADRs as `AdrSummary` array via authenticated request
- [ ] 1.5 Re-listing after creating a second ADR shows both sorted newest-edited first

### Phase 2: Frontend List Plumbing

#### Automated

- [x] 2.1 `cd frontend && pnpm run typecheck` — 3e7015e
- [x] 2.2 `cd frontend && pnpm run lint` — 3e7015e
- [x] 2.3 `cd frontend && pnpm run test -- adr.store.test.ts` — 3e7015e

#### Manual

- [ ] 2.4 Workspace page triggers `GET /api/adrs` on visit with authenticated session

### Phase 3: Card UI & Workspace Integration

#### Automated

- [x] 3.1 `cd frontend && pnpm run typecheck` — 7bc00c9
- [x] 3.2 `cd frontend && pnpm run lint` — 7bc00c9
- [x] 3.3 `cd frontend && pnpm run test -- adr-card.test.ts` — 7bc00c9

#### Manual

- [ ] 3.4 Card grid shows title, status badge, last-edited; empty state for zero ADRs
- [ ] 3.5 Clicking a card opens correct ADR editor page

### Phase 4: Status-Aware Editor & Navigation

#### Automated

- [ ] 4.1 `cd frontend && pnpm run typecheck`
- [ ] 4.2 `cd frontend && pnpm run lint`
- [ ] 4.3 `cd frontend && pnpm run test`
- [ ] 4.4 `just test-backend`

#### Manual

- [ ] 4.5 `in_review` ADR opens read-only with banner; draft ADR remains editable
- [ ] 4.6 Back link returns to workspace with refreshed card data after edits
