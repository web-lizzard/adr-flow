# First AI Review Annotations Implementation Plan

## Overview

Implement S-04: a one-shot AI review flow where a user submits a draft ADR, the backend transitions it to `in_review`, an async worker runs AI review through an LLM adapter, validated annotations are persisted, and the Nuxt editor polls until the ADR reaches `after_review` and displays the annotations.

The plan keeps this slice focused on review annotations only. Publishing reviewed ADRs to `proposed` remains S-05.

## Current State Analysis

The codebase already has the domain vocabulary and persistence columns needed for review results: `ReviewResult`, three annotation kinds, `ADRSubmittedForReview`, `AIReviewCompleted`, `adrs.review_annotations`, `adrs.reviewed_at`, and `events.processed_at`. The missing pieces are the submit command/API, event-store read/mark methods, async dispatch runtime, production-safe review validation, LLM adapter boundary, API response fields, frontend submit/polling, and annotation display.

Frontend ADR editing is already wired through a Pinia store and editor page. `in_review` is read-only today, which matches the review wait state, but the PRD requires `after_review` to be editable without re-review. There is no annotation UI yet.

## Desired End State

A logged-in user can open a draft ADR, click "Publish for review", immediately see the ADR lock into `in_review`, and wait on the same page while the frontend polls a lightweight status endpoint. When review completes, the page refetches the ADR, status becomes `after_review`, the editor is editable again, and a separate annotation panel shows actionable `missing_section`, `inconsistency`, and `conciseness` items.

If the LLM call or validation fails, the ADR remains recoverable in `in_review` with review error metadata exposed by the status endpoint. The worker uses at-least-once event processing and idempotent handlers so restart/replay does not duplicate completed reviews.

### Key Discoveries:

- The architecture already defines the async path: `ADRSubmittedForReview -> RunAiReview -> LLM adapter -> AIReviewCompleted -> projection update` in `context/foundation/application-architecture.md`.
- `backend/application/ports/event_store.py` only supports `append`; S-04 needs unprocessed-event loading and marking to make `events.processed_at` useful.
- `backend/application/ports/adr_repository.py` and `backend/infrastructure/api/schemas/adr.py` do not expose `review_annotations`, `reviewed_at`, or review error/status metadata.
- F-01 review-quality logic currently lives under `backend/tests/review_quality/`; production runtime must not import from `tests`.
- `frontend/app/pages/workspace/adr/[id].vue` already blocks edits during `in_review`, while the PRD says `after_review` should be editable.
- `frontend/composables/useApi.ts` and `frontend/app/stores/adr.ts` are the existing API/store seams for submit, polling, and response mapping.

## What We're NOT Doing

- Publishing an `after_review` ADR to `proposed`; that is S-05.
- Re-reviewing after edits in `after_review`.
- Inline CodeMirror annotation overlays.
- SSE, WebSockets, webhooks, or email completion notification.
- Configurable ADR section conventions or heading aliases.
- Full LLM-as-judge semantic scoring for inconsistency quality.
- A general-purpose distributed worker system; the MVP uses in-process async dispatch with persisted replay.
- A visible progress percentage or hard SLA for review duration.

## Implementation Approach

Build backend-first, then frontend. First make the data contracts safe: review metadata, production validation, event-store replay contracts, and API schemas. Then add the submit command, async handler, OpenAI-compatible local adapter, OpenRouter adapter, fake reviewer, dispatcher wiring, and failure handling. Finally, add the Nuxt submit/poll/display workflow and end-to-end verification across success, validation failure, provider failure, post-response dispatch, and replay/idempotency cases.

## Critical Implementation Details

**Submitted content snapshot:** `ADRSubmittedForReview` should carry the ADR content snapshot accepted for review, not just the ADR ID. This preserves the PRD contract that review evaluates the ADR as it was when the user clicked "Publish for review" and avoids adding an unscoped read path only for the worker.

**Failure state:** A failed review remains `in_review` and records structured review error metadata. The worker marks the triggering event processed only after either `AIReviewCompleted` or a terminal `AIReviewFailed` projection update succeeds, preventing infinite replay loops for permanently invalid output.

**Validation boundary:** Runtime code must use production-safe review validation under `domain/` or `application/`, not `backend/tests/review_quality/`. Test fixtures and aggregate metrics can remain under tests.

**Post-response dispatch boundary:** The TaskGroup bus must not run review work inside the FastAPI request/transaction lifecycle. The submit route returns `202` after the command commits, then schedules dispatch through a post-response/lifespan-managed bus. Tests must prove the handler is not invoked before the response lifecycle boundary is crossed.

## Phase 1: Backend Review Contracts And Validation

### Overview

Add the durable contracts the rest of the slice depends on: review response fields, review error metadata, production-safe validation, event-store replay primitives, and config for the LLM provider.

### Changes Required:

#### 1. Review metadata schema and migration

**File**: `backend/infrastructure/adapters/persistence/migrations/versions/003_review_error_metadata.py`

**Intent**: Store recoverable review failure details without inventing another status or overloading annotation payloads.

**Contract**: Add nullable `adrs.review_error` JSONB. The payload represents the last terminal worker failure for the current review attempt, with fields such as `source_event_id`, `code`, `message`, and `failed_at`.

#### 2. ORM and metadata tests

**File**: `backend/infrastructure/adapters/persistence/models.py`

**Intent**: Keep SQLAlchemy metadata aligned with the migration.

**Contract**: `Adr` exposes nullable JSONB `review_error`. `backend/tests/infrastructure/adapters/persistence/test_models.py` verifies the column type and nullability.

#### 3. Domain events

**File**: `backend/domain/adr/events.py`

**Intent**: Make submitted review work self-contained and record terminal failures as events.

**Contract**: Extend `ADRSubmittedForReview` to include the submitting `user_id` and `content` snapshot. Add `AIReviewFailed` carrying `adr_id`, `source_event_id`, `code`, and `message`. Keep `AIReviewCompleted` carrying `ReviewResult`.

#### 4. Read models and API schemas

**File**: `backend/application/ports/adr_repository.py`

**Intent**: Let query handlers and API routes expose review annotations and review status metadata from the projection.

**Contract**: Extend `AdrReadModel` with `review_annotations`, `reviewed_at`, and `review_error`.

**File**: `backend/infrastructure/api/schemas/adr.py`

**Intent**: Define the public API shape for review results and polling.

**Contract**: Add response models for review annotations, full ADR review fields, and a review status response containing at least `status`, `reviewed_at`, optional `review_error`, and optional annotation counts.

#### 5. Projection and repository contracts

**File**: `backend/application/ports/adr_projection.py`

**Intent**: Separate review lifecycle writes from content updates.

**Contract**: Add projection methods for marking an ADR `in_review`, applying a completed `ReviewResult`, and recording review failure metadata.

**File**: `backend/infrastructure/adapters/persistence/projections/adr_projection.py`

**Intent**: Implement status transitions and review persistence at the projection boundary.

**Contract**: `mark_in_review` sets status to `in_review`, clears previous review annotations/error, and updates `updated_at`. `apply_review_result` sets status to `after_review`, writes `review_annotations` and `reviewed_at`, clears `review_error`, and updates `updated_at`. `record_review_failure` leaves status `in_review` and writes `review_error`.

**File**: `backend/infrastructure/adapters/persistence/repositories/adr_repository.py`

**Intent**: Include review fields in all read model mappings.

**Contract**: `_to_read_model` deserializes `review_annotations`, `reviewed_at`, and `review_error` without changing ownership filters.

#### 6. Event-store replay contracts

**File**: `backend/application/ports/event_store.py`

**Intent**: Support at-least-once async processing with startup replay.

**Contract**: Add an event envelope/read model that exposes the durable event row ID plus methods to load unprocessed events and mark an event processed.

**File**: `backend/infrastructure/adapters/persistence/event_store.py`

**Intent**: Implement the outbox-style event read/mark behavior against `events.processed_at`.

**Contract**: Load unprocessed events in deterministic order with a limit, deserialize payloads through a known event type map, and mark individual event rows processed only after their handler succeeds or records terminal failure.

#### 7. Production review validation

**File**: `backend/application/review_quality.py`

**Intent**: Move runtime-safe validation out of test-only modules.

**Contract**: Provide validation that checks annotation actionability by kind and verifies `missing_section` coverage against `find_missing_or_empty_sections(markdown)`. Return structured failures that the worker can use for retry/error metadata.

#### 8. Provider settings

**File**: `backend/infrastructure/config.py`

**Intent**: Make provider configuration explicit and testable.

**Contract**: Add settings for an explicit provider mode such as `fake`, `openai_compatible`, or `openrouter`; provider API keys/base URLs; model name; and timeout. Local development should support an OpenAI-compatible API endpoint via base URL configuration, while automated tests can still use the fake reviewer without a live key.

**File**: `backend/pyproject.toml`

**Intent**: Ensure provider adapters have a production async HTTP client dependency.

**Contract**: Promote `httpx` to main dependencies and implement provider network calls with `httpx.AsyncClient`, not the synchronous client. Refresh `uv.lock` respecting the repository release-age policy.

### Success Criteria:

#### Automated Verification:

- Migration applies cleanly: `cd backend && uv run alembic upgrade head`
- Metadata and persistence tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/`
- Review validation tests pass: `cd backend && uv run pytest tests/review_quality/ tests/domain/adr/test_required_sections.py`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- Inspect the generated API schema for review annotation and review-status response fields.
- Confirm production code imports no modules from `backend/tests/`.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Submit API, Async Worker, And LLM Adapter

### Overview

Implement the backend review workflow: submit command and route, post-response async event dispatch, `RunAiReview` handler, fake reviewer, OpenAI-compatible local adapter, OpenRouter adapter, retry-on-invalid-output, and failure recording.

### Changes Required:

#### 1. Submit-for-review command

**File**: `backend/application/commands/submit_adr_for_review.py`

**Intent**: Encapsulate the user action that starts review and moves the ADR into `in_review`.

**Contract**: `SubmitAdrForReviewCommand(adr_id, user_id)` and handler. The handler loads the owned ADR, allows only `draft`, creates `ADRSubmittedForReview` with content snapshot, appends the event, updates projection to `in_review`, and returns enough event/envelope information for the route or dispatcher to schedule work only after the transaction succeeds and the HTTP response lifecycle boundary is reached.

#### 2. Review status query

**File**: `backend/application/queries/get_adr_review_status.py`

**Intent**: Give the frontend a lightweight polling read that does not fetch the full ADR body every interval.

**Contract**: `GetAdrReviewStatusQuery(adr_id, user_id)` and handler returning the owned ADR's status, `reviewed_at`, `review_error`, and annotation counts.

#### 3. LLM reviewer port

**File**: `backend/application/ports/llm_reviewer.py`

**Intent**: Keep provider details outside application logic and make tests deterministic.

**Contract**: `LlmReviewer` protocol with an async method that accepts ADR markdown and returns `ReviewResult`.

#### 4. Run AI review handler

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Process `ADRSubmittedForReview` asynchronously and persist either completed review output or terminal failure.

**Contract**: The handler calls `LlmReviewer`, validates output, retries once on provider/validation failure, appends `AIReviewCompleted` on success, applies the review projection, appends `AIReviewFailed` on terminal failure, records failure metadata with the triggering envelope ID, and remains idempotent if the ADR is already `after_review` or already has terminal failure metadata whose `source_event_id` matches the triggering envelope ID.

#### 5. Runtime dispatcher

**File**: `backend/application/runtime/dispatcher.py`

**Intent**: Provide a small handler registry and event dispatch loop for persisted domain events.

**Contract**: Register event type to handler, dispatch newly appended events after commit and after the FastAPI response has been handed off, and replay unprocessed events on startup. Unknown event types should be logged and marked or skipped according to a clear policy that prevents blocking known review events.

#### 6. Messaging adapter

**File**: `backend/infrastructure/messaging/task_group_bus.py`

**Intent**: Run event handlers asynchronously using the MVP `asyncio.TaskGroup` approach from the architecture.

**Contract**: Accept domain events/envelopes from application runtime, schedule handlers after the request lifecycle, and keep errors observable without crashing the FastAPI request path. The bus should be lifespan-managed so task execution can outlive the request handler but still shut down cleanly with the app.

#### 7. Fake reviewer

**File**: `backend/infrastructure/llm/fake_reviewer.py`

**Intent**: Make local development and tests independent of a live provider key.

**Contract**: Return deterministic `ReviewResult` objects that satisfy the runtime validator for common missing-section cases and include representative inconsistency/conciseness annotations when useful.

#### 8. OpenAI-compatible local adapter

**File**: `backend/infrastructure/llm/openai_compatible.py`

**Intent**: Support local development against an OpenAI-compatible API endpoint without changing application code.

**Contract**: Use settings-driven base URL, API key if required by the local endpoint, model, and timeout. Perform all network calls with `httpx.AsyncClient`, request structured JSON, parse it into `ReviewResult`, and raise typed provider/parse errors for the worker retry path.

#### 9. OpenRouter adapter

**File**: `backend/infrastructure/llm/openrouter.py`

**Intent**: Implement the production LLM provider behind the `LlmReviewer` port.

**Contract**: Use settings-driven API key, model, base URL if needed, and timeout. Perform all network calls with `httpx.AsyncClient`, request structured JSON, parse it into `ReviewResult`, and raise typed provider/parse errors for the worker retry path.

#### 10. API route and dependencies

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Expose submit and polling endpoints through the existing ADR router.

**Contract**: Add `POST /api/adrs/{adr_id}/submit-review` returning `202`, and `GET /api/adrs/{adr_id}/review-status`. Preserve ownership checks through command/query handlers. Map invalid status to `400`, missing ADR to `404`, and auth failures to existing auth behavior. The submit route must schedule review dispatch after response handoff, not inline before returning `202`.

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Resolve new handlers from `app.state`.

**Contract**: Add dependencies for submit and review-status handlers.

#### 11. Bootstrap wiring

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Wire the new command/query handlers, reviewer implementation, dispatcher, and startup replay.

**Contract**: Select fake, OpenAI-compatible local, or OpenRouter reviewer from settings, register `RunAiReview` for `ADRSubmittedForReview`, replay unprocessed events during lifespan startup, initialize the lifespan-managed TaskGroup bus, and dispose HTTP clients and bus resources cleanly on shutdown.

### Success Criteria:

#### Automated Verification:

- Submit command tests pass: `cd backend && uv run pytest tests/application/commands/test_submit_adr_for_review.py`
- Run-review handler tests pass: `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py`
- Post-response dispatch lifecycle tests pass: `cd backend && uv run pytest tests/infrastructure/messaging/test_task_group_bus.py tests/infrastructure/api/test_adr_api.py`
- API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py`
- Event-store and unit-of-work tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- With fake reviewer enabled, submit a draft via API and confirm status moves to `in_review` immediately, the `202` response is not delayed by review work, then status moves to `after_review` with annotations.
- Simulate an invalid fake/provider output and confirm status remains `in_review` with review error metadata visible from `review-status`.
- Restart the API with an unprocessed review event and confirm replay processes it once.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Frontend Submit, Polling, And Annotation Panel

### Overview

Add the user-facing review workflow in Nuxt: submit CTA, read-only wait state, polling status endpoint, refetch on completion, editable `after_review`, and a simple annotation panel.

### Changes Required:

#### 1. API client contracts

**File**: `frontend/composables/useApi.ts`

**Intent**: Add typed client functions for the new backend review endpoints.

**Contract**: Extend `AdrResponse` with review annotations, `reviewed_at`, and `review_error`. Add `ReviewAnnotation`, `ReviewStatusResponse`, `submitAdrForReview(id)`, and `fetchAdrReviewStatus(id)`.

#### 2. ADR store review state

**File**: `frontend/app/stores/adr.ts`

**Intent**: Keep submit, polling updates, and annotation mapping close to existing ADR state.

**Contract**: Extend `Adr` with `reviewAnnotations`, `reviewedAt`, and `reviewError`. Add `submitForReview(id)` that calls the API and reloads/updates current ADR. Add a lightweight status refresh action used by polling.

#### 3. ADR composable exports

**File**: `frontend/app/composables/useAdr.ts`

**Intent**: Expose the new store review actions to the editor page without bypassing the store.

**Contract**: Re-export submit and review-status actions plus current review fields through existing computed wrappers.

#### 4. Persistence gating

**File**: `frontend/app/composables/useAdrPersistence.ts`

**Intent**: Prevent background autosave paths from fighting the review lock state.

**Contract**: Gate blur, `pagehide`, and `visibilitychange` persistence on review editability so no `/save` request is attempted after an ADR enters `in_review`. The submit flow must await any dirty save before calling `submit-review`, then reload or clear dirty state from the server response path.

#### 5. Polling composable

**File**: `frontend/app/composables/useAdrReviewPolling.ts`

**Intent**: Poll while an ADR is `in_review` and stop as soon as it completes or fails.

**Contract**: Use `@vueuse/core` interval utilities or Nuxt lifecycle hooks to poll every few seconds, optionally back off after repeated polls, stop on unmount, stop when status is no longer `in_review`, and call `adr.load(id)` after completion to fetch full annotations.

#### 6. Annotation panel component

**File**: `frontend/app/components/adr/AdrReviewAnnotations.vue`

**Intent**: Show review output without adding inline editor overlays.

**Contract**: Render grouped or clearly labeled annotations by kind. Each item shows message, optional location, and optional suggestion. Empty state is allowed only when `after_review` has no annotations.

#### 7. Editor page integration

**File**: `frontend/app/pages/workspace/adr/[id].vue`

**Intent**: Add the submit/review UX to the existing ADR editor.

**Contract**: Show "Publish for review" only for `draft`, disable it while loading/dirty save is pending, save dirty changes before submit, show simple read-only reviewing copy while `in_review`, poll using the new composable, keep `after_review` editable, prevent autosave/beacon persistence while `in_review`, and display the annotation panel when review annotations or review error metadata exist. **Addendum (impl-review):** also show the panel for all `after_review` ADRs so the component can render its "No review annotations" empty state after a clean review.

### Success Criteria:

#### Automated Verification:

- Store tests pass: `cd frontend && pnpm run test -- tests/adr.store.test.ts`
- Editor page tests pass, including no blur/beacon-style save while `in_review`: `cd frontend && pnpm run test -- tests/adr-editor-page.test.ts`
- Annotation component tests pass: `cd frontend && pnpm run test -- tests/adr-review-annotations.test.ts`
- Frontend lint passes: `cd frontend && pnpm run lint`
- Frontend typecheck passes: `cd frontend && pnpm run typecheck`

#### Manual Verification:

- Draft page shows "Publish for review"; clicking it saves pending edits and starts review.
- `in_review` page is read-only and shows simple reviewing copy while polling.
- When polling sees completion, the page refetches and shows `after_review` annotations.
- `after_review` ADR remains editable and saving does not trigger another review.
- Review failure metadata appears as a clear recoverable error state.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: End-to-End Verification And Guardrails

### Overview

Verify the review loop as a product slice: happy path, invalid model output, provider failure, event replay, ownership isolation, and the F-01 quality gate over fixture ADRs.

### Changes Required:

#### 1. Backend quality-gate tests

**File**: `backend/tests/review_quality/test_runtime_validation.py`

**Intent**: Prove the production validator enforces the same actionability and missing-section constraints as F-01.

**Contract**: Cover valid output, missing required section annotation, invalid kind-specific fields, and aggregate fixture recall meeting the PRD threshold for deterministic/fake outputs.

#### 2. Backend API flow tests

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: Lock the end-to-end HTTP behavior for submit and polling.

**Contract**: Cover authenticated submit, unauthenticated submit, other-user access, invalid status submit, immediate `in_review`, status polling, successful annotation exposure, and failure metadata exposure.

#### 3. Worker replay/idempotency tests

**File**: `backend/tests/application/runtime/test_dispatcher.py`

**Intent**: Prove at-least-once processing is safe enough for MVP.

**Contract**: Cover replay of unprocessed events, marking after success, retry once on invalid output, terminal failure recording, and no duplicate review result when a completed ADR is replayed.

#### 4. TaskGroup bus lifecycle tests

**File**: `backend/tests/infrastructure/messaging/test_task_group_bus.py`

**Intent**: Prove review work runs after the FastAPI request lifecycle, not inline inside the submit request.

**Contract**: Cover that `POST /submit-review` can return `202` before the review handler starts or completes, dispatch is scheduled only after the command transaction succeeds, and bus-managed tasks can continue after the route handler returns while still shutting down cleanly with application lifespan.

#### 5. Provider adapter tests

**File**: `backend/tests/infrastructure/llm/test_openai_compatible.py`

**Intent**: Verify the local OpenAI-compatible adapter uses async HTTP and parses structured review output.

**Contract**: Mock `httpx.AsyncClient` or use `MockTransport` to assert async request behavior, base URL/model configuration, successful `ReviewResult` parsing, provider errors, and parse errors.

**File**: `backend/tests/infrastructure/llm/test_openrouter.py`

**Intent**: Verify the OpenRouter adapter follows the same async LLM reviewer contract with provider-specific configuration.

**Contract**: Mock `httpx.AsyncClient` or use `MockTransport` to assert async request behavior, authorization headers, model configuration, successful `ReviewResult` parsing, provider errors, and parse errors.

#### 6. Frontend flow tests

**File**: `frontend/tests/adr-editor-page.test.ts`

**Intent**: Verify the visible review workflow on the editor page.

**Contract**: Cover submit CTA visibility, read-only `in_review`, polling-driven refetch, annotation panel display, editable `after_review`, and no submit CTA outside `draft`.

#### 7. Documentation and environment examples

**File**: `.env.example`

**Intent**: Document backend review provider settings for local development.

**Contract**: Add commented provider mode, local OpenAI-compatible base URL/key, OpenRouter API key, model, and timeout variables without committing secrets.

**File**: `deploy/gcp/secrets.env.example`

**Intent**: Keep deployment secret docs aligned with backend settings.

**Contract**: Confirm `OPENROUTER_API_KEY` remains documented and add any new required non-secret provider configuration elsewhere if needed.

### Success Criteria:

#### Automated Verification:

- Backend review-quality tests pass: `cd backend && uv run pytest tests/review_quality/`
- Backend API and runtime tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py tests/application/`
- TaskGroup bus lifecycle tests pass: `cd backend && uv run pytest tests/infrastructure/messaging/test_task_group_bus.py`
- Provider adapter tests pass: `cd backend && uv run pytest tests/infrastructure/llm/`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`
- Frontend review tests pass: `cd frontend && pnpm run test -- tests/adr.store.test.ts tests/adr-editor-page.test.ts tests/adr-review-annotations.test.ts`
- Frontend lint passes: `cd frontend && pnpm run lint`
- Frontend typecheck passes: `cd frontend && pnpm run typecheck`

#### Manual Verification:

- Run the full local flow with the local OpenAI-compatible provider or fake reviewer: create ADR, edit, publish for review, wait, see `after_review` annotations, edit after review, and confirm no re-review starts.
- Run one failure scenario with fake invalid output and confirm the page shows recoverable review error metadata.
- Confirm submit returns quickly and review work continues after the request returns.
- Confirm no live OpenRouter key is required for automated tests or local OpenAI-compatible development.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before treating S-04 as complete.

---

## Testing Strategy

### Unit Tests:

- Submit command status guards and emitted event payload.
- Runtime review validator for missing-section coverage and kind-specific actionability.
- `RunAiReview` handler success, retry, terminal failure, and idempotency.
- Provider adapters use `httpx.AsyncClient` and parse structured output.
- Frontend store mapping for annotations, review status, and submit action.
- Annotation component rendering for all three kinds.

### Integration Tests:

- Persistence projection/repository writes and reads review annotations, reviewed timestamp, and review error metadata.
- Event-store load/mark behavior over `events.processed_at`.
- FastAPI submit and review-status endpoints with auth and ownership checks.
- TaskGroup bus scheduling after the submit request lifecycle.
- Frontend editor page submit/poll/refetch workflow with mocked API functions.

### Manual Testing Steps:

1. Start the app with the local OpenAI-compatible provider mode or fake reviewer mode.
2. Register/login, create an ADR, fill content with at least one missing/empty section.
3. Click "Publish for review" and confirm the editor locks in `in_review`.
4. Wait for polling to complete and confirm `after_review` annotations appear.
5. Edit the reviewed ADR and confirm save works without re-review.
6. Switch the provider/fake reviewer to invalid/failing mode and confirm recoverable error metadata appears while status remains `in_review`.

## Performance Considerations

MVP scale is small, and review is one-shot per ADR. Polling should use a modest interval with cleanup on unmount to avoid unnecessary requests. The backend worker should process a bounded number of unprocessed events on startup and must not block FastAPI request handling on LLM latency; dispatch happens after the submit response lifecycle, and provider calls use `httpx.AsyncClient`.

## Migration Notes

Additive migration only: `adrs.review_error` nullable JSONB. Existing ADR rows remain valid. If the branch has no deployed review flow yet, event payload changes for `ADRSubmittedForReview` do not need backward-compatible shims beyond defensive deserialization in tests.

## References

- Related research: `context/changes/first-ai-review-annotations/research.md`
- Product scope: `context/foundation/roadmap.md`
- PRD review flow: `context/foundation/prd.md`
- Backend architecture: `context/foundation/application-architecture.md`
- Prior quality harness: `context/archive/2026-06-16-review-quality-checks/plan.md`
- Backend command pattern: `backend/application/commands/create_adr.py`
- Backend update guard: `backend/application/commands/update_adr_content.py`
- Event store seam: `backend/infrastructure/adapters/persistence/event_store.py`
- ADR projection seam: `backend/infrastructure/adapters/persistence/projections/adr_projection.py`
- ADR API router: `backend/infrastructure/api/routers/adr.py`
- TaskGroup bus target: `backend/infrastructure/messaging/task_group_bus.py`
- LLM adapter targets: `backend/infrastructure/llm/openai_compatible.py`, `backend/infrastructure/llm/openrouter.py`
- Frontend editor page: `frontend/app/pages/workspace/adr/[id].vue`
- Frontend ADR store: `frontend/app/stores/adr.ts`
- Frontend API wrapper: `frontend/composables/useApi.ts`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend Review Contracts And Validation

#### Automated

- [x] 1.1 Migration applies cleanly: `cd backend && uv run alembic upgrade head` — 79c4428
- [x] 1.2 Metadata and persistence tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/` — 79c4428
- [x] 1.3 Review validation tests pass: `cd backend && uv run pytest tests/review_quality/ tests/domain/adr/test_required_sections.py` — 79c4428
- [x] 1.4 Backend lint passes: `cd backend && uv run ruff check .` — 79c4428
- [x] 1.5 Backend type check passes: `cd backend && uv run ty check` — 79c4428

#### Manual

- [x] 1.6 Inspect the generated API schema for review annotation and review-status response fields — 79c4428
- [x] 1.7 Confirm production code imports no modules from `backend/tests/` — 79c4428

### Phase 2: Submit API, Async Worker, And LLM Adapter

#### Automated

- [x] 2.1 Submit command tests pass: `cd backend && uv run pytest tests/application/commands/test_submit_adr_for_review.py` — ee26d36
- [x] 2.2 Run-review handler tests pass: `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py` — ee26d36
- [x] 2.3 Post-response dispatch lifecycle tests pass: `cd backend && uv run pytest tests/infrastructure/messaging/test_task_group_bus.py tests/infrastructure/api/test_adr_api.py` — ee26d36
- [x] 2.4 API tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py` — ee26d36
- [x] 2.5 Event-store and unit-of-work tests pass: `cd backend && uv run pytest tests/infrastructure/adapters/persistence/` — ee26d36
- [x] 2.6 Backend lint passes: `cd backend && uv run ruff check .` — ee26d36
- [x] 2.7 Backend type check passes: `cd backend && uv run ty check` — ee26d36

#### Manual

- [x] 2.8 With fake reviewer or local OpenAI-compatible provider enabled, submit a draft via API and confirm status moves to `in_review` immediately, the `202` response is not delayed by review work, then status moves to `after_review` with annotations
- [x] 2.9 Simulate an invalid fake/provider output and confirm status remains `in_review` with review error metadata visible from `review-status`
- [x] 2.10 Restart the API with an unprocessed review event and confirm replay processes it once

### Phase 3: Frontend Submit, Polling, And Annotation Panel

#### Automated

- [x] 3.1 Store tests pass: `cd frontend && pnpm run test -- tests/adr.store.test.ts` — 7d6dcf3
- [x] 3.2 Editor page tests pass, including no blur/beacon-style save while `in_review`: `cd frontend && pnpm run test -- tests/adr-editor-page.test.ts` — 7d6dcf3
- [x] 3.3 Annotation component tests pass: `cd frontend && pnpm run test -- tests/adr-review-annotations.test.ts` — 7d6dcf3
- [x] 3.4 Frontend lint passes: `cd frontend && pnpm run lint` — 7d6dcf3
- [x] 3.5 Frontend typecheck passes: `cd frontend && pnpm run typecheck` — 7d6dcf3

#### Manual

- [x] 3.6 Draft page shows "Publish for review"; clicking it saves pending edits and starts review
- [x] 3.7 `in_review` page is read-only and shows simple reviewing copy while polling
- [x] 3.8 When polling sees completion, the page refetches and shows `after_review` annotations
- [x] 3.9 `after_review` ADR remains editable and saving does not trigger another review
- [x] 3.10 Review failure metadata appears as a clear recoverable error state

### Phase 4: End-to-End Verification And Guardrails

#### Automated

- [x] 4.1 Backend review-quality tests pass: `cd backend && uv run pytest tests/review_quality/`
- [x] 4.2 Backend API and runtime tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py tests/application/`
- [x] 4.3 TaskGroup bus lifecycle tests pass: `cd backend && uv run pytest tests/infrastructure/messaging/test_task_group_bus.py`
- [x] 4.4 Provider adapter tests pass: `cd backend && uv run pytest tests/infrastructure/llm/`
- [x] 4.5 Backend lint passes: `cd backend && uv run ruff check .`
- [x] 4.6 Backend type check passes: `cd backend && uv run ty check`
- [x] 4.7 Frontend review tests pass: `cd frontend && pnpm run test -- tests/adr.store.test.ts tests/adr-editor-page.test.ts tests/adr-review-annotations.test.ts`
- [x] 4.8 Frontend lint passes: `cd frontend && pnpm run lint`
- [x] 4.9 Frontend typecheck passes: `cd frontend && pnpm run typecheck`

#### Manual

- [x] 4.10 Run the full local flow with the local OpenAI-compatible provider or fake reviewer: create ADR, edit, publish for review, wait, see `after_review` annotations, edit after review, and confirm no re-review starts
- [x] 4.11 Run one failure scenario with fake invalid output and confirm the page shows recoverable review error metadata
- [x] 4.12 Confirm submit returns quickly and review work continues after the request returns
- [x] 4.13 Confirm no live OpenRouter key is required for automated tests or local OpenAI-compatible development
