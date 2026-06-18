# Publish After Review Implementation Plan

## Overview

Complete S-05 — the north-star slice that finishes Success Criterion #1. Users can already edit ADRs in `after_review` without re-triggering AI review (S-04). This plan adds the missing **publish transition** (`after_review` → `proposed`): backend command + projection + API, frontend Publish CTA + UX polish, and tests.

## Current State Analysis

Roughly half of S-05 is implemented:

- **Done:** `after_review` editing (backend `update_adr_content`, frontend editor, blur/beacon save), review annotations panel, `AdrStatus.PROPOSED` enum, `ADRPublished` domain event, event-store type registry entry.
- **Missing:** `publish_adr` command, `mark_proposed` projection, `ADRPublished` in sync projection registry, API route, frontend API/store/page wiring, publish tests.

The submit-for-review vertical slice is the reference pattern. Publish differs by being **synchronous** (append → `mark_proposed` → `mark_processed`, return `204`) with a guard for `after_review` only.

### Key Discoveries:

- `backend/application/commands/submit_adr_for_review.py` — template for command structure, guards, logging, UoW transaction.
- `backend/application/commands/create_adr.py` — sync `mark_processed` pattern publish must follow (submit intentionally omits this for async AI dispatch).
- `backend/application/ports/adr_projection.py` — `mark_in_review` clears review metadata; `mark_proposed` must **only** update `status` + `updated_at` and preserve `review_annotations`, `reviewed_at`, `review_error`.
- `backend/infrastructure/adapters/persistence/event_store.py:36-42` — `SYNC_PROJECTION_EVENT_TYPES` must include `"ADRPublished"`.
- `frontend/app/pages/workspace/adr/[id].vue` — submit button/handler pattern; draft CTA is **"Publish for review"**; S-05 needs separate **"Publish"** label for `after_review`.
- `frontend/app/composables/useAdrPersistence.ts` — editable guard blocks only `in_review`; `proposed` editing already works at persistence layer.
- No toast infrastructure exists in `frontend/app/` today; user requested toast on successful publish.

## Desired End State

A logged-in user completes the full lifecycle in one session:

`draft` → (Publish for review) → `in_review` → (AI review) → `after_review` → (edit + Publish) → `proposed`

After publish:

- Status badge shows `proposed`.
- Toast confirms successful publish.
- Editor remains editable; blur/beacon save continues to work.
- Review annotations panel remains visible when annotations exist (existing `showReviewPanel` logic already handles this via annotation count).
- Helper text is status-aware (not generic "Draft changes save…" for all states).

**Verification:** Manual E2E through `proposed`; automated command, projection, API, and frontend unit tests pass.

## What We're NOT Doing

- Re-review or async dispatch on publish (`ADRPublished` must not register in `EventDispatcher`).
- `accepted` / `superseded` statuses or approval workflows.
- Automated full-lifecycle integration test (draft → proposed in one test file).
- Post-MVP list/history UX changes beyond what S-03 delivers.
- Making `proposed` read-only (FR-005 permits editing except in `in_review`).
- Returning updated ADR body from publish API (use `204` + client `load(id)` like submit pattern).

## Implementation Approach

**Backend-first, two phases.** Phase 1 delivers the publish command vertical slice with tests. Phase 2 wires the frontend CTA mirroring `submitForReview`, adds minimal toast infrastructure, status-aware copy, and frontend tests.

Mirror submit-for-review at every layer:

```
submit_adr_for_review.py  →  POST /adrs/{id}/submit-review  →  202
publish_adr.py            →  POST /adrs/{id}/publish         →  204
```

```
useApi.submitAdrForReview  →  store.submitForReview  →  useAdr  →  [id].vue
useApi.publishAdr            →  store.publish          →  useAdr  →  [id].vue
```

## Critical Implementation Details

- **`mark_proposed` must not clear review fields.** Unlike `mark_in_review` (which nulls review metadata), publish preserves annotations so the panel can remain visible in `proposed`.
- **Publish blocking mirrors submit.** Add `isPublishing` ref; include it in `isReadOnly` and pass to `useAdrPersistence` third arg so editor + save are disabled during the API call. Save-if-dirty before publish in `onPublish`.
- **Toast is net-new UI infra.** Add shadcn toast/sonner via `shadcn-nuxt` (`Toast` + `Toaster` in default layout); scope initial usage to publish success only.

## Phase 1: Backend Publish Transition

### Overview

Add `mark_proposed` projection, `PublishAdrCommand` handler with status guard and sync `mark_processed`, register `ADRPublished` as a sync projection event, expose `POST /api/adrs/{adr_id}/publish`, and cover legal + illegal transitions with tests.

### Changes Required:

#### 1. Projection port and SQL adapter

**File**: `backend/application/ports/adr_projection.py`

**Intent**: Declare the projection method commands call to apply the `proposed` status after `ADRPublished`.

**Contract**: Add `async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> None: ...` alongside existing status transition methods.

**File**: `backend/infrastructure/adapters/persistence/projections/adr_projection.py`

**Intent**: Implement `mark_proposed` on `SqlAdrProjection`, updating only `status` and `updated_at`.

**Contract**: `UPDATE adrs SET status = 'proposed', updated_at = :updated_at WHERE id = :adr_id`. Do not modify `review_annotations`, `reviewed_at`, or `review_error`.

#### 2. Publish command handler

**File**: `backend/application/commands/publish_adr.py` (new)

**Intent**: Own the `after_review` → `proposed` transition: load ADR, guard status, emit `ADRPublished`, apply projection, mark event processed synchronously.

**Contract**:

- `PublishAdrCommand(adr_id: UUID, user_id: UUID)`
- `PublishAdrCommandHandler.handle` loads via `find_by_id_for_owner` → `AdrNotFound` if missing
- Guard: `existing.status == AdrStatus.AFTER_REVIEW` only → `DomainError("ADR can only be published from after_review status")`
- Event: `ADRPublished(adr_id=AdrId(...), occurred_at=updated_at)` — no `user_id` or `content` in payload
- UoW: `append` → `mark_proposed` → `mark_processed` (same transaction)
- Structured logging keys: `command.publish_adr.{started,rejected,event_appended,completed}`

#### 3. Event store sync registry

**File**: `backend/infrastructure/adapters/persistence/event_store.py`

**Intent**: Ensure `ADRPublished` is treated as a sync projection event (never picked up by async worker replay).

**Contract**: Add `"ADRPublished"` to `SYNC_PROJECTION_EVENT_TYPES` frozenset.

#### 4. API route, bootstrap, dependencies

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Expose publish endpoint with same error mapping as submit-review.

**Contract**: `POST /{adr_id}/publish`, `status_code=204`, auth via `get_current_user_id`, handler via `get_publish_adr_handler`. Map `AdrNotFound` → 404, `DomainError` → 400. Empty `Response`.

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Construct and attach `PublishAdrCommandHandler(uow_factory, adr_repository)` to `app.state.publish_adr_handler`. Do **not** register `ADRPublished` on `EventDispatcher`.

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Provide FastAPI dependency for the publish handler.

**Contract**: `get_publish_adr_handler(request) -> request.app.state.publish_adr_handler`

#### 5. Backend tests

**File**: `backend/tests/application/commands/test_publish_adr.py` (new)

**Intent**: Unit-test command handler with fakes — happy path, not found, illegal status transitions.

**Contract**: Assert event type `ADRPublished`, `mark_proposed` called, `mark_processed` called. Test publish rejected from `draft`, `in_review`, `proposed`.

**File**: `backend/tests/infrastructure/adapters/persistence/test_adr_projection_review.py`

**Intent**: Integration-test `mark_proposed` preserves review metadata after `apply_review_result`.

**Contract**: After `mark_proposed`, row has `status = 'proposed'` and `review_annotations` / `reviewed_at` unchanged.

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: API integration tests for publish — happy path, wrong status (400), missing ADR (404), unauthenticated (401), other user's ADR (404).

**Contract**: Seed `after_review` ADR (via submit + wait helper or direct DB update), `POST /api/adrs/{id}/publish` → 204, `GET` → `status == "proposed"`.

**File**: Existing command test fakes (`test_submit_adr_for_review.py`, `test_create_adr.py`, `test_update_adr_content.py`, `test_run_ai_review.py`)

**Intent**: Add no-op `mark_proposed` to all `FakeAdrProjection` stubs so Protocol surface stays complete.

**File**: `backend/tests/infrastructure/adapters/persistence/test_event_store.py`

**Intent**: Confirm `ADRPublished` is skipped by async replay (extend or sibling to existing sync-projection skip test).

### Success Criteria:

#### Automated Verification:

- Ruff check passes: `cd backend && uv run ruff check .`
- Type check passes: `cd backend && uv run ty check`
- Command tests pass: `cd backend && uv run pytest tests/application/commands/test_publish_adr.py -v`
- Projection tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_adr_projection_review.py -v`
- API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k publish -v`
- Full backend suite passes: `cd backend && uv run pytest`

#### Manual Verification:

- Via API client (curl/httpx): create ADR → submit for review → wait for `after_review` → `POST /publish` → `GET` returns `proposed` with review annotations intact
- Illegal transitions return 400 with clear message

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to Phase 2.

---

## Phase 2: Frontend Publish CTA and UX

### Overview

Wire `publishAdr` through API client → store → composable → editor page. Add Publish button for `after_review`, status-aware helper copy, toast on success, publish-in-flight blocking (mirror submit), and frontend tests.

### Changes Required:

#### 1. API client

**File**: `frontend/composables/useApi.ts`

**Intent**: Add HTTP client for publish endpoint.

**Contract**: `publishAdr(id: string): $fetch<void>(apiPath(\`/adrs/${id}/publish\`), { method: "POST" })`

#### 2. Store and composable

**File**: `frontend/app/stores/adr.ts`

**Intent**: Add store method that calls API and reloads current ADR (same pattern as `submitForReview`).

**Contract**: `publish(id: string)` — set `loading`, call `publishAdr(id)`, `await load(id)`, clear `loading` in `finally`. Export from store return object.

**File**: `frontend/app/composables/useAdr.ts`

**Intent**: Re-export `publish` from store for page consumption.

#### 3. Toast infrastructure

**Files**: `frontend/app/components/ui/toast/` (via shadcn-nuxt add), `frontend/app/layouts/default.vue` (or app root)

**Intent**: Provide minimal toast capability for publish success feedback.

**Contract**: Install shadcn `toast` component; mount `<Toaster />` in default layout. Expose `useToast()` (or equivalent from shadcn-nuxt) for one-shot success messages.

#### 4. Editor page — Publish button and UX

**File**: `frontend/app/pages/workspace/adr/[id].vue`

**Intent**: Show Publish CTA in `after_review`, handle publish flow, update helper copy, show toast on success.

**Contract**:

- `showPublishButton` computed: `status === "after_review"`
- `isPublishing` ref; include in `isReadOnly` alongside `isSubmitting`
- Pass `isPublishing` (or combined blocking ref) to `useAdrPersistence` third argument
- `onPublish`: guard visibility + in-flight; clear `publishError`; set `isPublishing`; save-if-dirty → `adr.publish(id)` → toast success ("ADR published as proposed" or similar) → catch → `publishError` inline (mirror `onSubmitForReview`)
- Template: Publish button block with label **"Publish"** (distinct from draft **"Publish for review"**)
- Status-aware helper copy:
  - `draft`: "Draft changes save when you click away or leave this tab."
  - `after_review`: "Edit based on review feedback. Changes save when you click away or leave this tab."
  - `proposed`: "Changes save when you click away or leave this tab."
  - `in_review`: keep existing read-only message (unchanged)
- `showReviewPanel`: no change required — annotations persist and existing logic (`annotations.length > 0`) keeps panel visible in `proposed`

**File**: `frontend/app/composables/useAdrPersistence.ts`

**Intent**: Extend editable guard to respect publish-in-flight blocking.

**Contract**: Third optional ref blocks save/beacon when publishing (same as `isSubmitting`).

#### 5. Frontend tests

**File**: `frontend/tests/adr.store.test.ts`

**Intent**: Test `publish` calls API, reloads ADR, manages loading flag.

**Contract**: Mock `publishAdr` + `load`; assert `currentAdr.status` becomes `proposed` after publish.

**File**: `frontend/tests/adr-editor-page.test.ts`

**Intent**: Test page behavior for publish flow.

**Contract**:

- Publish button visible only in `after_review`; hidden in `draft` and `proposed`
- `onPublish` saves when dirty before calling publish
- Editor disabled during `isPublishing`
- Post-publish: status badge reflects `proposed`; editor remains editable
- Toast invoked on success (mock `useToast`)

### Success Criteria:

#### Automated Verification:

- ESLint passes: `cd frontend && pnpm run lint`
- Typecheck passes: `cd frontend && pnpm run typecheck`
- Store tests pass: `cd frontend && pnpm run test tests/adr.store.test.ts`
- Page tests pass: `cd frontend && pnpm run test tests/adr-editor-page.test.ts`
- Full frontend suite passes: `cd frontend && pnpm run test`

#### Manual Verification:

- E2E demo: login → new ADR → fill content → Publish for review → wait for annotations → edit in `after_review` → Publish → badge shows `proposed`, toast appears, annotations still visible, editor editable, blur-save works
- Confirm "Publish for review" (draft) and "Publish" (`after_review`) labels are distinct and unambiguous
- Publish error (e.g. wrong status via API tampering) shows inline error without toast

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that the E2E north-star flow works.

---

## Testing Strategy

### Unit Tests:

- **Backend command:** happy path, `AdrNotFound`, illegal status from `draft`/`in_review`/`proposed`, `mark_processed` asserted
- **Backend projection:** `mark_proposed` sets status, preserves review metadata
- **Frontend store:** publish API + reload + loading
- **Frontend page:** button visibility, save-before-publish, blocking during publish, post-publish editable state

### Integration Tests:

- **API:** publish from `after_review` → 204; wrong status → 400; ownership → 404; auth → 401
- **Event store:** `ADRPublished` excluded from async replay

### Manual Testing Steps:

1. Complete full lifecycle draft → proposed in browser
2. Verify toast + badge update on publish
3. Edit title/content in `proposed` and confirm blur-save persists
4. Reopen ADR from workspace list — status `proposed`, annotations visible
5. Attempt illegal publish via API (from `draft`) — 400 with clear message

## Performance Considerations

Publish is a single synchronous command (one event append + one projection update + `mark_processed`). No performance concerns at MVP scale. No new polling or async workers.

## Migration Notes

No data migration required. `ADRPublished` events may exist in event store from domain tests but no production publish events exist yet. Bootstrap replay will mark any unprocessed sync `ADRPublished` events processed on startup once added to `SYNC_PROJECTION_EVENT_TYPES`.

## References

- Related research: `context/changes/publish-after-review/research.md`
- Submit command template: `backend/application/commands/submit_adr_for_review.py`
- Submit API template: `backend/infrastructure/api/routers/adr.py:68-108`
- Editor page: `frontend/app/pages/workspace/adr/[id].vue`
- S-04 deferrals: `context/archive/2026-06-17-first-ai-review-annotations/plan.md`
- PRD: US-01, US-04, FR-005, FR-007, FR-009
- Roadmap: S-05 in `context/foundation/roadmap.md:129-139`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Backend Publish Transition

#### Automated

- [x] 1.1 Ruff check passes: `cd backend && uv run ruff check .` — 07446c3
- [x] 1.2 Type check passes: `cd backend && uv run ty check` — 07446c3
- [x] 1.3 Command tests pass: `cd backend && uv run pytest tests/application/commands/test_publish_adr.py -v` — 07446c3
- [x] 1.4 Projection tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_adr_projection_review.py -v` — 07446c3
- [x] 1.5 API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k publish -v` — 07446c3
- [x] 1.6 Full backend suite passes: `cd backend && uv run pytest` — 07446c3

#### Manual

- [x] 1.7 Via API client: after_review ADR publishes to proposed with review annotations intact — 07446c3
- [x] 1.8 Illegal transitions return 400 with clear message — 07446c3

### Phase 2: Frontend Publish CTA and UX

#### Automated

- [ ] 2.1 ESLint passes: `cd frontend && pnpm run lint`
- [ ] 2.2 Typecheck passes: `cd frontend && pnpm run typecheck`
- [ ] 2.3 Store tests pass: `cd frontend && pnpm run test tests/adr.store.test.ts`
- [ ] 2.4 Page tests pass: `cd frontend && pnpm run test tests/adr-editor-page.test.ts`
- [ ] 2.5 Full frontend suite passes: `cd frontend && pnpm run test`

#### Manual

- [ ] 2.6 E2E demo: full lifecycle draft → proposed with toast, editable proposed state, annotations visible
- [ ] 2.7 Publish for review vs Publish labels are distinct; publish error shows inline without toast
