# Draft Authoring & Persistence Implementation Plan

## Overview

Build S-02: the first ADR behavior slice. Users can create an ADR from the starter template, edit markdown in a CodeMirror editor, save on blur and on tab close/refresh, and recover saved content when they return. This is a full-stack vertical slice across backend domain, application, infrastructure, and frontend pages/stores/composables.

## Current State Analysis

**Backend (ready):** F-02 delivered the `adrs` ORM model with all columns (id, user_id, title, content, status, review_annotations, is_deleted, timestamps), the events table, ADR domain vocabulary (aggregate dataclass, six events including `ADRCreated` and `ADRContentUpdated`, value objects for status/content/title), and Alembic migrations. S-01 delivered JWT auth with `get_current_user_id`, the UoW + event store pattern (`RegisterUserCommandHandler` as the template), and `bootstrap.py` composition root.

**Backend (missing):** No ADR command handlers, query handlers, ports, projection adapters, read repositories, router, schemas, or bootstrap wiring. The UoW port exposes only `event_store` + `user_projection` — no `adr_projection`.

**Frontend (ready):** S-01 delivered auth store with `$fetch` + `apiPath` pattern, Nitro proxy (`/api/*` → FastAPI), protected `/workspace` page with auth middleware, and shadcn-vue primitives (Button, Card, Form, Input, Label). `@vueuse/core` ^14.3.0 is a dependency.

**Frontend (missing):** No ADR pages, stores, composables, editor component, or save-on-blur/unload patterns. No Textarea or CodeMirror dependency. No `beforeunload`/`visibilitychange` handlers anywhere.

### Key Discoveries:

- `aggregate_type` in existing auth uses PascalCase `"User"` while architecture doc specifies lowercase — S-02 will use lowercase `"adr"` and defer `"User"` normalization
- `sendBeacon` only supports POST, so a dedicated `POST /api/adrs/{id}/save` beacon endpoint is needed alongside the regular `PATCH /api/adrs/{id}`
- `vue-codemirror6` (v1.5.2) provides SSR-compatible Vue wrapper with `v-model` binding and native `@blur`/`@change` events
- Ownership enforcement belongs in command/query handlers (not routers), per architecture doc

## Desired End State

A logged-in user clicks "Create ADR" on the workspace page, enters a required title (validated for per-user uniqueness via a search endpoint), and is navigated to a new editor page at `/workspace/adr/{id}`. The editor shows a CodeMirror markdown editor pre-filled with the five-heading starter template (`## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences`), with the title editable inline above the editor. Work is automatically saved when the user clicks away (blur) or closes/refreshes the tab (unload via sendBeacon). Returning to the same URL recovers the latest saved content. The backend persists every save as an `ADRContentUpdated` event + projection update in a single transaction. Title changes are also validated for uniqueness within the user's scope.

**Verification:** Enter title → Create ADR → edit content → blur (saves) → refresh page → content recovered. Close tab during edit → reopen URL → content recovered. Attempt duplicate title → error shown.

## What We're NOT Doing

- ADR list/cards view (S-03)
- Submit for AI review / status transitions beyond `draft` (S-04)
- Publish as `proposed` (S-05)
- Soft-delete (S-06)
- Continuous debounced autosave (per PRD speed decision)
- Rich WYSIWYG / split markdown preview pane
- Event dispatcher / startup replay wiring

## Implementation Approach

Follow the established vertical-slice pattern: backend persistence infrastructure → command/query handlers → API router → frontend store + editor. Each backend layer mirrors the `RegisterUser` / `GetCurrentUser` patterns. Frontend mirrors the auth store + `$fetch` pattern. CodeMirror provides the editor with markdown highlighting. Save-on-blur uses regular `$fetch` PATCH; save-on-unload uses `navigator.sendBeacon` POST to a dedicated beacon endpoint sharing the same command handler.

## Critical Implementation Details

### sendBeacon constraints

`navigator.sendBeacon` only sends POST requests, cannot set custom headers, and has a ~64 KiB payload limit. The beacon endpoint (`POST /api/adrs/{id}/save`) must accept a JSON `Blob` body and authenticate via the existing httpOnly session cookie (sent automatically on same-origin requests). The endpoint shares `UpdateAdrContentCommandHandler` with the regular PATCH route — no duplicate business logic.

### Title uniqueness

Title must be unique within a user's active (non-deleted) ADRs. Enforced in command handlers via a pre-check query (`find_by_title_for_owner`) before create/update. The search endpoint (`GET /api/adrs/search?q=...`) uses case-insensitive `ILIKE` matching for frontend title validation — the frontend calls this on title input to show real-time feedback before submission. The uniqueness check in the handler uses exact case-insensitive match (`lower(title) = lower(:title)`) as the authoritative guard.

### CodeMirror SSR

CodeMirror requires `document` and `window`. The editor component must be wrapped in `<ClientOnly>` in Nuxt or use a `.client.vue` filename convention. `vue-codemirror6` handles SSR internally but the extra guard prevents hydration mismatches.

---

## Phase 1: Backend Persistence Infrastructure

### Overview

Add the ADR starter template constant, AdrProjection and AdrRepository ports with SQL adapters, extend the UoW port and factory with `adr_projection`, and add ADR-specific domain errors. This phase delivers the persistence seams that command and query handlers plug into.

### Changes Required:

#### 1. Starter template constant

**File**: `backend/domain/adr/template.py` (new)

**Intent**: Define the canonical ADR starter template as a constant so `CreateAdrCommandHandler` and tests reference a single source of truth.

**Contract**: `ADR_STARTER_TEMPLATE: str` — the five-heading markdown string (`## Context\n\n## Options\n\n## Decision\n\n## Status\n\n## Consequences\n`).

#### 2. AdrProjection port

**File**: `backend/application/ports/adr_projection.py` (new)

**Intent**: Define the write-side projection port for inserting and updating ADR rows in the projection table, consumed by the UoW.

**Contract**: `AdrProjection(Protocol)` with `async def insert(self, adr_id, user_id, title, content, status, created_at, updated_at) -> None` and `async def update_content(self, adr_id, title, content, updated_at) -> None`.

#### 3. AdrProjection SQL adapter

**File**: `backend/infrastructure/adapters/persistence/projections/adr_projection.py` (new)

**Intent**: Implement the AdrProjection port using SQLAlchemy ORM operations on the existing `Adr` model, mirroring `SqlUserProjection`.

**Contract**: `SqlAdrProjection(AdrProjection)` — takes shared `AsyncSession` from UoW. `insert` does `session.add(Adr(...))`. `update_content` does `session.execute(update(Adr).where(Adr.id == adr_id).values(...))`.

#### 4. AdrRepository port

**File**: `backend/application/ports/adr_repository.py` (new)

**Intent**: Define the read-side port for loading ADRs, with an `AdrReadModel` dataclass for the query handler to return.

**Contract**: `AdrReadModel` frozen dataclass with `id`, `user_id`, `title`, `content`, `status`, `is_deleted`, `created_at`, `updated_at`. `AdrRepository(Protocol)` with:
- `async def find_by_id_for_owner(self, adr_id: UUID, user_id: UUID) -> AdrReadModel | None` — ownership-filtered load
- `async def find_by_title_for_owner(self, title: str, user_id: UUID) -> AdrReadModel | None` — exact case-insensitive title match for uniqueness validation
- `async def search_by_title(self, user_id: UUID, query: str) -> list[AdrReadModel]` — ILIKE lexical search within user's non-deleted ADRs

#### 5. AdrRepository SQL adapter

**File**: `backend/infrastructure/adapters/persistence/repositories/adr_repository.py` (new)

**Intent**: Implement the AdrRepository port with ownership-filtered queries, mirroring `SqlUserRepository`.

**Contract**: `SqlAdrRepository(AdrRepository)` — takes `async_sessionmaker`. `find_by_id_for_owner` filters `WHERE id = :adr_id AND user_id = :user_id AND is_deleted = false`. `find_by_title_for_owner` filters `WHERE lower(title) = lower(:title) AND user_id = :user_id AND is_deleted = false`. `search_by_title` filters `WHERE user_id = :user_id AND is_deleted = false AND title ILIKE '%' || :query || '%'`. Maps ORM `Adr` row to `AdrReadModel` via `_to_read_model` helper.

#### 6. Extend UoW port with adr_projection

**File**: `backend/application/ports/unit_of_work.py`

**Intent**: Add `adr_projection: AdrProjection` to the `UnitOfWork` protocol so command handlers can write ADR projections in the same transaction as event appends.

**Contract**: `UnitOfWork` protocol gains `adr_projection: AdrProjection` field.

#### 7. Extend SqlUnitOfWorkFactory with adr_projection

**File**: `backend/infrastructure/adapters/persistence/unit_of_work.py`

**Intent**: Wire `SqlAdrProjection` into the UoW factory's `begin()` context manager, mirroring `SqlUserProjection`.

**Contract**: `SqlUnitOfWork.__init__` accepts and exposes `adr_projection: SqlAdrProjection`. `SqlUnitOfWorkFactory.begin()` creates `SqlAdrProjection(session)` and passes it to `SqlUnitOfWork`.

#### 8. ADR domain errors

**File**: `backend/domain/errors.py`

**Intent**: Add `AdrNotFound`, `AdrAccessDenied`, and `AdrTitleAlreadyExists` error classes for use in command/query handlers.

**Contract**: `class AdrNotFound(DomainError): pass`, `class AdrAccessDenied(DomainError): pass`, and `class AdrTitleAlreadyExists(DomainError): pass` — all inheriting auto-derived `kind` from the base class.

#### 9. Export template from domain/adr

**File**: `backend/domain/adr/__init__.py`

**Intent**: Re-export the starter template constant so consumers import from the package root.

**Contract**: Add `ADR_STARTER_TEMPLATE` to imports and `__all__`.

### Success Criteria:

#### Automated Verification:

- All new files pass `uv run ruff check .` and `uv run ruff format --check .`
- Type checking passes: `uv run ty check`
- Existing tests still pass: `uv run pytest`
- UoW protocol is structurally compatible: existing `RegisterUserCommandHandler` tests pass unchanged

#### Manual Verification:

- Code review confirms AdrProjection port/adapter mirror UserProjection pattern
- Code review confirms AdrRepository port/adapter mirror UserRepository pattern
- UoW extension is additive — no changes to existing User projection behavior

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Backend Command + Query Handlers

### Overview

Add `CreateAdrCommandHandler` (creates draft with starter template, validates title uniqueness), `UpdateAdrContentCommandHandler` (saves title + content with status guard and title uniqueness), `GetAdrQueryHandler` (loads ADR for authenticated owner), and `SearchAdrsByTitleQueryHandler` (lexical title search for the validation/search endpoint). These are the four use cases the API router will call.

### Changes Required:

#### 1. CreateAdrCommandHandler

**File**: `backend/application/commands/create_adr.py` (new)

**Intent**: Handle ADR creation — validate title uniqueness within the user's scope, generate an ID, set status to `draft`, fill content with the starter template, emit `ADRCreated`, and write the projection. Mirrors `RegisterUserCommandHandler` pattern.

**Contract**: `CreateAdrCommand(frozen dataclass)` with `user_id: UUID` and `title: str` (required). `CreateAdrCommandHandler` takes `uow_factory: UnitOfWorkFactory` and `adr_repository: AdrRepository` via `__init__`. `handle()` checks `adr_repository.find_by_title_for_owner(title, user_id)` — raises `AdrTitleAlreadyExists` if a match exists — then opens UoW, appends `ADRCreated` event with `aggregate_type="adr"`, inserts via `uow.adr_projection.insert(...)`, returns `UUID`.

#### 2. UpdateAdrContentCommandHandler

**File**: `backend/application/commands/update_adr_content.py` (new)

**Intent**: Handle content/title saves — load the existing ADR, verify ownership and status guard (not `in_review`), emit `ADRContentUpdated`, update the projection. Used by both PATCH and beacon-save endpoints.

**Contract**: `UpdateAdrContentCommand(frozen dataclass)` with `adr_id: UUID`, `user_id: UUID`, `title: str | None`, `content: str | None`. `UpdateAdrContentCommandHandler` takes `uow_factory: UnitOfWorkFactory` and `adr_repository: AdrRepository`. `handle()` loads ADR via `adr_repository.find_by_id_for_owner(...)`, raises `AdrNotFound` if missing, raises `AdrAccessDenied` if not owner, raises `DomainError("Cannot edit ADR in review")` if status is `in_review`. If `title` is provided and differs from current title, checks uniqueness via `adr_repository.find_by_title_for_owner(title, user_id)` — raises `AdrTitleAlreadyExists` if a different ADR holds that title. Appends `ADRContentUpdated` event, updates projection with changed fields.

#### 3. GetAdrQueryHandler

**File**: `backend/application/queries/get_adr.py` (new)

**Intent**: Load a single ADR for the authenticated owner, raising `AdrNotFound` if it doesn't exist or isn't owned by the caller.

**Contract**: `GetAdrQuery(frozen dataclass)` with `adr_id: UUID` and `user_id: UUID`. `GetAdrQueryHandler` takes `adr_repository: AdrRepository`. `handle()` returns `AdrReadModel` or raises `AdrNotFound`.

#### 4. SearchAdrsByTitleQueryHandler

**File**: `backend/application/queries/search_adrs_by_title.py` (new)

**Intent**: Lexical search across the user's ADR titles for the frontend title validation and search UI. Simple Python-backed ILIKE search — no external search engine.

**Contract**: `SearchAdrsByTitleQuery(frozen dataclass)` with `user_id: UUID` and `query: str`. `SearchAdrsByTitleQueryHandler` takes `adr_repository: AdrRepository`. `handle()` returns `list[AdrReadModel]` (may be empty). Searches non-deleted ADRs for the authenticated user where title matches the query via case-insensitive substring match.

### Success Criteria:

#### Automated Verification:

- All new files pass `uv run ruff check .` and `uv run ruff format --check .`
- Type checking passes: `uv run ty check`
- Existing tests still pass: `uv run pytest`

#### Manual Verification:

- Code review confirms CreateAdr follows RegisterUser pattern (UoW transaction, event + projection)
- Code review confirms CreateAdr checks title uniqueness before write
- Code review confirms UpdateAdrContent validates ownership and title uniqueness before write
- Code review confirms GetAdr filters by user_id and is_deleted
- Code review confirms SearchAdrsByTitle returns matches for the calling user only

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Backend API Layer + Integration Tests

### Overview

Add the ADR router with five endpoints (create, get, update, beacon-save, search), Pydantic request/response schemas, dependency injection functions, bootstrap wiring, and integration tests covering the full request cycle including title uniqueness.

### Changes Required:

#### 1. ADR API schemas

**File**: `backend/infrastructure/api/schemas/adr.py` (new)

**Intent**: Define request/response Pydantic models for the ADR endpoints, mirroring `schemas/auth.py`.

**Contract**: `CreateAdrRequest(BaseModel)` with required `title: str` (min_length=1, stripped). `UpdateAdrRequest(BaseModel)` with `title: str | None = None` and `content: str | None = None`. `AdrResponse(BaseModel)` with `id: UUID`, `title: str`, `content: str`, `status: str`, `created_at: datetime`, `updated_at: datetime`. `CreateAdrResponse(BaseModel)` with `id: UUID`. `SearchAdrsResponse(BaseModel)` with `results: list[AdrSummary]` where `AdrSummary` has `id: UUID`, `title: str`, `status: str`, `updated_at: datetime`.

#### 2. ADR dependency injection functions

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Add `get_create_adr_handler`, `get_update_adr_content_handler`, `get_get_adr_handler`, and `get_search_adrs_handler` functions that read from `request.app.state`, mirroring existing auth handler getters.

**Contract**: Four new functions following the `get_register_user_handler` pattern — each returns the pre-constructed handler from `app.state`.

#### 3. ADR router

**File**: `backend/infrastructure/api/routers/adr.py` (new)

**Intent**: HTTP driving adapter for ADR operations. Five endpoints sharing handlers via `Depends()`.

**Contract**:
- `POST /adrs` (201) — calls `CreateAdrCommandHandler` with required title, returns `CreateAdrResponse` with the new ADR ID
- `GET /adrs/{adr_id}` — calls `GetAdrQueryHandler`, returns `AdrResponse`
- `PATCH /adrs/{adr_id}` — calls `UpdateAdrContentCommandHandler`, returns `AdrResponse` (re-fetched via GetAdr after update)
- `POST /adrs/{adr_id}/save` — beacon-save endpoint, same as PATCH but accepts POST for `sendBeacon` compatibility, returns 204 No Content
- `GET /adrs/search?q={query}` — calls `SearchAdrsByTitleQueryHandler`, returns `SearchAdrsResponse` with matching ADR summaries

All endpoints use `Depends(get_current_user_id)` for auth. Domain errors map to HTTP: `AdrNotFound` → 404, `AdrAccessDenied` → 403, `AdrTitleAlreadyExists` → 409 Conflict.

#### 4. Bootstrap wiring

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Construct ADR command/query handlers with their dependencies in the composition root, store on `app.state`, and mount the ADR router under the `/api` prefix.

**Contract**: Create `SqlAdrRepository(session_factory)`, construct `CreateAdrCommandHandler(uow_factory, adr_repository)`, `UpdateAdrContentCommandHandler(uow_factory, adr_repository)`, `GetAdrQueryHandler(adr_repository)`, `SearchAdrsByTitleQueryHandler(adr_repository)`. Store all on `app.state`. Import and include `adr_router` on the api router.

#### 5. Integration tests

**File**: `backend/tests/infrastructure/api/test_adr.py` (new)

**Intent**: End-to-end tests covering the ADR API through the full request cycle, mirroring `test_auth.py` test patterns.

**Contract**: Test cases:
- Create ADR with required title returns 201 with `id`, starter template content, and `draft` status
- Create ADR without title returns 422 validation error
- Create ADR with duplicate title (same user) returns 409 Conflict
- Create ADR with same title as another user's ADR succeeds (per-user scope)
- Get ADR returns the created ADR with correct content
- PATCH ADR updates title and/or content
- PATCH ADR with duplicate title returns 409 Conflict
- Beacon-save (POST /save) updates content and returns 204
- Get after PATCH returns updated content (persistence verification)
- Search by title returns matching ADRs for the authenticated user
- Search by title returns empty for non-matching query
- Search does not return other users' ADRs
- Unauthenticated requests return 401
- Accessing another user's ADR returns 404 (ownership isolation)
- PATCH on `in_review` status returns error (status guard — set up via direct DB manipulation since S-02 has no review endpoint)

### Success Criteria:

#### Automated Verification:

- All new files pass `uv run ruff check .` and `uv run ruff format --check .`
- Type checking passes: `uv run ty check`
- All tests pass: `uv run pytest` (existing + new integration tests)
- ADR integration tests verify create → update → reload cycle

#### Manual Verification:

- Manual curl/httpie test: `POST /api/adrs` with title and session cookie returns 201
- Manual curl/httpie test: `POST /api/adrs` with same title returns 409
- Manual curl/httpie test: `GET /api/adrs/{id}` returns starter template content
- Manual curl/httpie test: `GET /api/adrs/search?q=partial` returns matching results
- Manual curl/httpie test: `PATCH /api/adrs/{id}` with changed content, then GET confirms update

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Frontend Editor + Save Persistence

### Overview

Install CodeMirror packages, build the frontend ADR integration: API client functions (including search), Pinia store, CodeMirror markdown editor component, editor page at `/workspace/adr/[id].vue`, save-on-blur + save-on-unload composable, "Create ADR" entry point with required title input and uniqueness validation, and frontend tests.

### Changes Required:

#### 1. Install CodeMirror dependencies

**File**: `frontend/package.json`

**Intent**: Add CodeMirror 6 packages and the Vue wrapper for the markdown editor.

**Contract**: `pnpm add vue-codemirror6 codemirror @codemirror/lang-markdown @codemirror/language @codemirror/view @codemirror/state`

#### 2. Add shadcn Textarea component

**Intent**: Add the shadcn-vue Textarea component for the title input styling consistency (or use existing Input — decide during implementation based on title field needs).

**Contract**: Run `npx shadcn-vue@latest add textarea` if needed, or use existing `Input` component for the single-line title field.

#### 3. Extend API client with ADR functions

**File**: `frontend/composables/useApi.ts`

**Intent**: Add typed API helper functions for ADR operations, following the `fetchHealth` pattern.

**Contract**: Export `createAdr(title: string)`, `fetchAdr(id: string)`, `updateAdr(id: string, data: { title?: string; content?: string })`, `searchAdrs(query: string)` — all using `$fetch` + `apiPath`. Add `AdrResponse`, `CreateAdrResponse`, `AdrSummary`, and `SearchAdrsResponse` types.

#### 4. ADR Pinia store

**File**: `frontend/app/stores/adr.ts` (new)

**Intent**: Manage ADR editor state — load, create, track dirty state, save. Mirrors the auth store pattern.

**Contract**: `useAdrStore` with `currentAdr` ref, `loading` ref, `isDirty` ref. Actions: `create(title: string)` calls POST with required title, navigates to editor; `load(id)` calls GET, populates state; `save()` calls PATCH if dirty, clears dirty flag; `searchByTitle(query: string)` calls search endpoint for uniqueness validation. Store tracks `lastSavedContent` and `lastSavedTitle` to compute dirtiness.

#### 5. CodeMirror editor component

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue` (new)

**Intent**: Wrap `vue-codemirror6` with markdown language support, exposing `v-model` and `@blur` event. Client-only via `.client.vue` naming.

**Contract**: Props: `modelValue: string`. Emits: `update:modelValue`, `blur`. Uses `markdown({ base: markdownLanguage })` from `@codemirror/lang-markdown`, `basicSetup` from `codemirror`, line wrapping. Styled with Tailwind classes for consistent appearance.

#### 6. Editor page

**File**: `frontend/app/pages/workspace/adr/[id].vue` (new)

**Intent**: Protected editor page that loads the ADR by ID, shows a title input + CodeMirror editor, and wires save-on-blur + save-on-unload.

**Contract**: `definePageMeta({ middleware: ["auth"] })`. On mount, loads ADR via store. Title rendered as `<Input>` above the editor. CodeMirror editor fills the main content area. `<ClientOnly>` wrapper with a skeleton fallback around the editor. Uses `useAdrPersistence` composable for save behavior.

#### 7. Save persistence composable

**File**: `frontend/app/composables/useAdrPersistence.ts` (new)

**Intent**: Encapsulate save-on-blur (regular `$fetch` PATCH) and save-on-unload (`navigator.sendBeacon` POST to `/api/adrs/{id}/save`) logic in a reusable composable.

**Contract**: `useAdrPersistence(adrId: Ref<string>, store: ReturnType<typeof useAdrStore>)` — registers blur handler that calls `store.save()`, registers `pagehide` and `visibilitychange` listeners that fire `sendBeacon` with a JSON Blob payload if dirty. Uses `@vueuse/core` `useEventListener` for lifecycle-safe event registration. Cleans up on unmount.

#### 8. Workspace "Create ADR" entry point

**File**: `frontend/app/pages/workspace/index.vue`

**Intent**: Replace the placeholder text with a "Create ADR" form that requires a title before creation. The title input validates uniqueness in real-time via the search endpoint (debounced) and shows an error if the title already exists.

**Contract**: Add a form with an `Input` for title (required, min 1 char) and a "Create" `Button`. On title input change (debounced ~300ms): call `searchAdrs(title)` and check for exact match — show inline error "An ADR with this title already exists" if found. On submit: `await adrStore.create(title)` → `navigateTo(/workspace/adr/${id})`. Show loading state during creation. Disable submit if title is empty or duplicate detected.

#### 9. useAdr composable

**File**: `frontend/app/composables/useAdr.ts` (new)

**Intent**: Thin wrapper over `useAdrStore` for template convenience, mirroring `useAuth`.

**Contract**: Returns computed refs for `currentAdr`, `loading`, `isDirty`, and action delegates for `create`, `load`, `save`, `searchByTitle`.

#### 10. Frontend tests

**File**: `frontend/tests/adr.store.test.ts` (new)

**Intent**: Unit tests for the ADR store, mirroring `auth.store.test.ts` mocking patterns.

**Contract**: Test cases:
- `create(title)` calls POST /api/adrs with title and sets currentAdr
- `create(title)` propagates 409 error for duplicate titles
- `load(id)` calls GET /api/adrs/{id} and populates state
- `save()` calls PATCH /api/adrs/{id} when dirty
- `save()` skips API call when not dirty
- `searchByTitle(query)` calls GET /api/adrs/search and returns results
- Dirty tracking: changes to content/title set isDirty

### Success Criteria:

#### Automated Verification:

- All new files pass `pnpm run lint` and `pnpm run format:check`
- Type checking passes: `pnpm run typecheck`
- Frontend tests pass: `pnpm run test`
- Build succeeds: `pnpm run build`

#### Manual Verification:

- Navigate to `/workspace`, enter title, click "Create" → redirected to `/workspace/adr/{id}` with starter template
- Attempt to create with duplicate title → inline error shown, submit disabled
- Edit content in CodeMirror editor, click outside (blur) → network tab shows PATCH request
- Refresh page → content recovered from API
- Edit content, close tab → reopen same URL → content recovered (sendBeacon fired on close)
- Title input updates, blur saves title alongside content
- Change title to an existing title → 409 error shown
- Editor renders with markdown syntax highlighting (headings styled differently)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Backend: ADR command handlers with mock UoW and repositories (verify event emission, projection calls, ownership checks, status guard)
- Frontend: ADR store with mocked `$fetch` (verify API calls, state management, dirty tracking)

### Integration Tests:

- Backend: Full HTTP request cycle through FastAPI test client (create → update → get → ownership isolation)
- Frontend: Build verification (Nuxt build succeeds with CodeMirror SSR handled)

### Manual Testing Steps:

1. Register/login, navigate to workspace
2. Enter title, click "Create" — verify redirect to editor with starter template
3. Attempt to create another ADR with the same title — verify error shown
4. Edit content, click outside editor — verify save via network tab
5. Refresh page — verify content recovered
6. Edit content, close browser tab — reopen URL — verify content recovered
7. Edit title, blur title field — verify title saved
8. Change title to an existing title — verify error shown
9. Open a second browser/incognito — verify ADR is not accessible (ownership isolation)
10. Search for ADR by partial title — verify results returned

## Performance Considerations

- CodeMirror 6 is tree-shakeable; `basicSetup` adds ~150 KB gzipped but provides essential editor UX (undo/redo, line numbers, bracket matching)
- `sendBeacon` has a ~64 KiB payload limit — sufficient for ADR markdown content in MVP (ADRs are typically 1-5 KB)
- ADR projection queries use the `ix_adrs_user_id` index for ownership-filtered reads

## Migration Notes

No new database migrations needed — the `adrs` table already exists from F-02 with all required columns. The UoW port extension is additive and doesn't affect existing User projection behavior.

## References

- Related research: `context/changes/draft-authoring-persistence/research.md`
- Architecture: `context/foundation/application-architecture.md`
- Write pattern: `backend/application/commands/register_user.py`
- Read pattern: `backend/application/queries/get_current_user.py`
- Router pattern: `backend/infrastructure/api/routers/auth.py`
- UoW pattern: `backend/infrastructure/adapters/persistence/unit_of_work.py`
- Store pattern: `frontend/app/stores/auth.ts`
- Test pattern: `frontend/tests/auth.store.test.ts`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend Persistence Infrastructure

#### Automated

- [x] 1.1 All new files pass ruff check and ruff format
- [x] 1.2 Type checking passes: ty check
- [x] 1.3 Existing tests still pass: pytest
- [x] 1.4 UoW protocol structurally compatible: RegisterUser tests pass unchanged

#### Manual

- [ ] 1.5 Code review confirms AdrProjection mirrors UserProjection pattern
- [ ] 1.6 Code review confirms AdrRepository mirrors UserRepository pattern
- [ ] 1.7 UoW extension is additive — no changes to existing User projection

### Phase 2: Backend Command + Query Handlers

#### Automated

- [ ] 2.1 All new files pass ruff check and ruff format
- [ ] 2.2 Type checking passes: ty check
- [ ] 2.3 Existing tests still pass: pytest

#### Manual

- [ ] 2.4 Code review confirms CreateAdr follows RegisterUser pattern
- [ ] 2.5 Code review confirms CreateAdr checks title uniqueness before write
- [ ] 2.6 Code review confirms UpdateAdrContent validates ownership and title uniqueness
- [ ] 2.7 Code review confirms GetAdr filters by user_id and is_deleted
- [ ] 2.8 Code review confirms SearchAdrsByTitle returns matches for calling user only

### Phase 3: Backend API Layer + Integration Tests

#### Automated

- [ ] 3.1 All new files pass ruff check and ruff format
- [ ] 3.2 Type checking passes: ty check
- [ ] 3.3 All tests pass: pytest (existing + new integration tests)
- [ ] 3.4 ADR integration tests verify create → update → reload cycle

#### Manual

- [ ] 3.5 curl POST /api/adrs with title returns 201 with id
- [ ] 3.6 curl POST /api/adrs with same title returns 409
- [ ] 3.7 curl GET /api/adrs/{id} returns starter template content
- [ ] 3.8 curl GET /api/adrs/search?q=partial returns matching results
- [ ] 3.9 curl PATCH /api/adrs/{id} updates content, GET confirms

### Phase 4: Frontend Editor + Save Persistence

#### Automated

- [ ] 4.1 All new files pass lint and format:check
- [ ] 4.2 Type checking passes: typecheck
- [ ] 4.3 Frontend tests pass: pnpm run test
- [ ] 4.4 Build succeeds: pnpm run build

#### Manual

- [ ] 4.5 Enter title, create ADR from workspace → editor shows starter template
- [ ] 4.6 Attempt duplicate title → inline error shown, submit disabled
- [ ] 4.7 Edit content, blur → PATCH fires in network tab
- [ ] 4.8 Refresh page → content recovered
- [ ] 4.9 Edit content, close tab → reopen URL → content recovered
- [ ] 4.10 Title input saves alongside content
- [ ] 4.11 Change title to existing title → error shown
- [ ] 4.12 Markdown syntax highlighting visible in editor
