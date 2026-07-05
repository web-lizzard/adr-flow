# Error Status Implementation Plan

## Overview

Introduce `review_failed` as a fifth ADR lifecycle status for system-level AI review failures, with a dedicated `RetryAdrForReviewCommandHandler` and `POST /api/adrs/{id}/retry-review` endpoint. Soften merge-validation failures so reviews complete to `after_review` with ratings and annotations (user decides next steps). Expose `DomainError.kind` via a global API exception handler and persisted `review_error.kind` for async failures; frontend projects user-facing copy and CTA visibility from `kind`. Update frontend badge, editor lock, error panel, and retry CTA.

## Current State Analysis

Failed AI reviews leave the ADR in `in_review` with `review_error` populated. Domain `fail_review` does not change status; projection `record_review_failure` writes only `review_error`. Users cannot edit (`AdrEditWhileInReview`), cannot resubmit (`submit_for_review` accepts only `draft`), and idempotency blocks replay (`duplicate_failure`). Frontend stops polling when `review_error` appears but still shows “In review”, keeps the editor locked, and surfaces only `reviewError.message` with no retry guidance.

Merge validation failures in `AdrReviewService` raise `AdrReviewFailedError`, which the handler maps to `validation_failed` and the same stuck state — despite ratings/annotations being available to deliver.

### Key Discoveries:

- `fail_review` / `_with_review_failed` do not set status (`backend/domain/adr/aggregate.py:214-219`)
- `RunAiReviewHandler._fail_review` hardcodes `code = "validation_failed"` for all exceptions (`backend/application/handlers/run_ai_review.py:167`)
- `submit_adr_for_review` is the template for new command wiring (`backend/application/commands/submit_adr_for_review.py`, `bootstrap.py`, `dependencies.py`, `routers/adr.py`)
- `mark_in_review` already clears `review_error` — retry infrastructure partially exists (`backend/infrastructure/adapters/persistence/projections/adr_projection.py:36-47`)
- Editor lock checks only `status === "in_review"` (`frontend/app/pages/workspace/adr/[id].vue:25-30`) — will naturally unlock once status is `review_failed`
- PRD non-goal limits MVP to 4 statuses (`context/foundation/prd.md:173`) — requires amendment

## Desired End State

When the AI review pipeline cannot deliver a result (LLM/provider exhaustion, unexpected infrastructure failure), the ADR transitions to `review_failed` with `review_error.code = "internal_error"` and a persisted `kind` derived from the originating exception (`adr_review_failed_error` for retryable pipeline failures; a stable fallback kind for unexpected errors). The user sees a destructive status badge, a structured error panel with reason and guidance (copy projected from `kind` on the frontend), and a “Try again” button when the frontend maps `kind` to a retryable action. Retry calls `POST /api/adrs/{id}/retry-review`, which emits a fresh `ADRSubmittedForReview` and re-queues `RunAiReviewHandler`.

When the review pipeline produces a merged result (even if merge validation would previously have failed), the ADR completes to `after_review` with section ratings and annotations — the user decides whether to edit or publish.

Existing stranded rows (`in_review` + non-null `review_error`) are auto-migrated to `review_failed` with backfilled `kind`.

### Verification:

- System failure during review → `GET /api/adrs/{id}` returns `status: "review_failed"`, `review_error.code: "internal_error"`, `review_error.kind` set
- `POST /api/adrs/{id}/retry-review` from `review_failed` → 202, status becomes `in_review`, `review_error` cleared, new review runs
- `POST /api/adrs/{id}/retry-review` from `draft` → 400 with `kind: "adr_invalid_retry_status"` (via global exception handler)
- Merge validation failure → `after_review` with `section_ratings` populated (no `review_error`)
- Frontend: `review_failed` badge, editor unlocked, retry CTA visible when `kind` maps to retry
- Alembic data migration moves stranded projection rows

## What We're NOT Doing

- Extending `SubmitAdrForReviewCommandHandler` to accept `review_failed` (dedicated retry handler per user preference)
- `provider_failed` as a separate error code (mapped to `internal_error`)
- `review_failed` transition for merge-validation / ADR-content issues (those complete to `after_review`)
- Support email/URL for `contact_admin` (placeholder copy only for MVP)
- `has_review_error` or error snippets on workspace list (`AdrSummary` unchanged)
- Rate limiting or backoff enforcement on retry endpoint
- Re-review flow for successful `after_review` ADRs (S-09 / conditional re-review — separate change)
- Event-store replay migration for historical `AIReviewFailed` events (projection data migration only)

## Implementation Approach

Backend-first in four phases: (1) domain status + softened validation gate + handler `internal_error` codes, (2) global `DomainError` API handler forwarding `kind`, retry command/API, projection `kind` persistence + migration, (3) frontend UX projecting copy from `kind`, (4) PRD amendment. The retry command mirrors `submit_adr_for_review` wiring but calls `retry_review()` guarded for `review_failed` only. `RunAiReviewHandler` maps failures to `internal_error`; Phase 2 persists exception `kind` on `review_error` for read paths.

## Critical Implementation Details

- **Event-sourcing consistency:** Domain `ReviewError` stays `code` + `message` only. Persist `kind` on `ReviewErrorMetadata` / projection JSON and on `AIReviewFailed` event payload (Phase 2) so async failures and replay stay aligned. Rehydrate fold for `AIReviewFailed` must set `status=REVIEW_FAILED` (today it leaves `in_review`).
- **API error contract:** Global FastAPI exception handler maps `DomainError` → HTTP 4xx with `kind` in the response body. Frontend projects copy/CTAs from `kind`; no `required_action` in domain.
- **Idempotency:** Retry emits a **new** `ADRSubmittedForReview` with a new stored event id. `duplicate_failure` skip keys on `source_event_id` — old failures do not block the new submit.
- **Validation gate change:** Removing the raise in `AdrReviewService.review_adr:111-120` is a behavioral change from R-01. Log `adr_review.validation_failed` at warning level and return the merged result. Update `test_adr_review_service` tests that expect raise on validation failure.

## Phase 1: Domain & Failure Taxonomy

### Overview

Add `review_failed` status, soften merge validation, and fix handler failure classification to `internal_error`. No `required_action` or `kind` in domain — those belong in application/API layers (Phase 2).

### Changes Required:

#### 1. Status enum

**File**: `backend/domain/adr/value_objects.py`

**Intent**: Add fifth lifecycle status.

**Contract**: `AdrStatus.REVIEW_FAILED = "review_failed"`. `ReviewError` remains `code` + `message` only (no `required_action`).

#### 2. Domain events

**File**: `backend/domain/adr/events.py`

**Intent**: No schema change in Phase 1 (`AIReviewFailed` keeps `code` + `message`). Phase 2 adds optional `kind` on the event for replay.

#### 3. Aggregate transitions

**File**: `backend/domain/adr/aggregate.py`

**Intent**: Failure changes status; add retry command method; keep edit guard blocking only `in_review`.

**Contract**:
- `_with_review_failed` sets `status=AdrStatus.REVIEW_FAILED` in addition to `review_error`
- `fail_review(code, message)` — no `required_action`
- New public `retry_review(updated_at)` — raises `AdrInvalidRetryStatus` unless `status == REVIEW_FAILED`; delegates to `_with_submitted_for_review` (same as submit: `in_review`, clears review fields)
- Rehydrate `AIReviewFailed` case sets `review_failed` from `code` + `message`

#### 4. Typed domain errors

**File**: `backend/domain/errors.py`

**Intent**: Typed guard for retry command; infrastructure failure type for review worker.

**Contract**: New `AdrInvalidRetryStatus`. `InternalError` (`kind=internal_error`) for non-retryable application invariant failures. `RetryableInternalError` (`kind=retryable_internal_error`) for LLM/provider/worker failures. Content gaps complete to `after_review` without raising.

#### 5. Review service — soften validation gate

**File**: `backend/application/services/adr_review_service.py`

**Intent**: Deliver ratings/annotations even when merge validation fails; user decides next steps.

**Contract**: When `validate_review_result` fails, log warning and return `result` instead of raising. Infrastructure failures after LLM retries raise `InternalError`.

#### 6. AI review handler — failure classification

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Map system failures to `internal_error` + `review_failed`.

**Contract**:
- Catch `RetryableInternalError` and `InternalError` → `_fail_review` with `code=type(error).kind`
- Catch other `Exception` → wrap as `RetryableInternalError`, then `_fail_review`
- Phase 2 persists `kind` matching `review_error.code` for frontend CTA mapping
- `_skip_reason`: treat `review_failed` like retryable state (do not skip new submits — only `duplicate_failure` per event id)

#### 7. Domain and handler tests

**Files**: `backend/tests/domain/test_adr_aggregate.py`, `backend/tests/domain/test_adr_rehydrate.py`, `backend/tests/application/handlers/test_run_ai_review.py`, `backend/tests/application/services/test_adr_review_service.py`

**Intent**: Lock in new status transitions, rehydration, failure codes, and softened validation.

**Contract**: Update assertions expecting `in_review` after failure to `review_failed`. Add `retry_review` happy path and guard tests. Add test that merge validation failure completes to `after_review` path (via handler integration test).

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_adr_rehydrate.py tests/application/handlers/test_run_ai_review.py tests/application/services/test_adr_review_service.py -q`
- `cd backend && uv run ruff check .`
- `cd backend && uv run ty check`

#### Manual Verification:

- N/A for this phase (no API/frontend yet)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Retry Command, API & Migration

### Overview

Add dedicated retry command handler and endpoint; global `DomainError` exception handler; persist and expose `kind` on review failures; update projection; migrate stranded rows.

### Changes Required:

#### 1. Global API exception handler

**Files**: `backend/infrastructure/api/exception_handlers.py` (new), `backend/infrastructure/bootstrap.py`

**Intent**: Centralize `DomainError` → HTTP mapping; forward `kind` in all 4xx error responses.

**Contract**:
- Register `@app.exception_handler(DomainError)` (or equivalent) on app creation
- Response body includes `kind` (from `DomainError.kind`), `message`, and stable HTTP status per error type
- Replace duplicated per-route `except DomainError` blocks in routers where the global handler covers them
- Command guard failures (e.g. `AdrInvalidRetryStatus` → 400) use the same shape

#### 2. Retry command handler

**File**: `backend/application/commands/retry_adr_for_review.py` (new)

**Intent**: Dedicated retry use case — do not extend `SubmitAdrForReviewCommandHandler`.

**Contract**: `RetryAdrForReviewCommand(adr_id, user_id)`, `RetryAdrForReviewResult(stored_event)`, `RetryAdrForReviewCommandHandler` mirroring submit handler structure: lock aggregate, rehydrate, ownership check (`AdrNotFound`), `adr.retry_review(updated_at)`, append `ADRSubmittedForReview`, call `mark_in_review`. Structured logs: `command.retry_adr_for_review.*`.

#### 3. Handler + metadata — persist `kind` on review failures

**Files**: `backend/application/handlers/run_ai_review.py`, `backend/application/review_metadata.py`, `backend/domain/adr/events.py`

**Intent**: Thread exception `kind` through async failure path (not domain `ReviewError`).

**Contract**:
- `RetryableInternalError` → `kind=retryable_internal_error` (frontend: retry CTA)
- `InternalError` → `kind=internal_error` (frontend: no retry / contact admin)
- Add `kind: str` to `AIReviewFailed`, `ReviewErrorMetadata`, and projection `review_error` JSON
- Handler derives `kind` from `type(exc).kind` when persisting failures

#### 4. Projection failure write

**File**: `backend/infrastructure/adapters/persistence/projections/adr_projection.py`

**Intent**: Failure updates status column, not just `review_error` JSON.

**Contract**: `record_review_failure` also sets `status=AdrStatus.REVIEW_FAILED.value` and persists `kind` in `review_error` JSON blob.

#### 5. API schemas

**File**: `backend/infrastructure/api/schemas/adr.py`

**Intent**: Expose `kind` on review errors for frontend projection.

**Contract**: Add `kind: str` to `ReviewErrorResponse`; update `from_metadata` factory.

#### 6. Router endpoint

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: New retry endpoint following existing POST action conventions.

**Contract**: `POST /{adr_id}/retry-review`, status 202, empty body (mirror `submit-review`). Map `AdrNotFound` → 404, `AdrInvalidRetryStatus` → 400 via global handler (`kind` in body).

#### 7. Composition root wiring

**Files**: `backend/infrastructure/bootstrap.py`, `backend/infrastructure/api/dependencies.py`

**Intent**: Register handler per 4-step checklist in `backend-application.mdc`.

**Contract**: `retry_adr_for_review_handler` on `app.state`; `get_retry_adr_for_review_handler` dependency.

#### 8. Data migration

**File**: `backend/infrastructure/adapters/persistence/migrations/versions/004_review_failed_status.py` (new)

**Intent**: Auto-migrate stranded projection rows.

**Contract**: Alembic revision `004_review_failed` revising `003_review_error`. `upgrade()`:
```sql
UPDATE adrs
SET status = 'review_failed',
    review_error = review_error || '{"kind": "adr_review_failed_error"}'::jsonb
WHERE status = 'in_review'
  AND review_error IS NOT NULL
  AND (review_error->>'kind') IS NULL;
```
Normalize legacy `code` from `validation_failed` to `internal_error` for migrated rows (system failures were mislabeled). `downgrade()` is best-effort reverse (document limitation).

#### 9. API and command tests

**Files**: `backend/tests/application/commands/test_retry_adr_for_review.py` (new), `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: Cover retry happy path, invalid status, auth, and migrated failure metadata shape.

**Contract**: Add `test_retry_review_from_review_failed_returns_202`, `test_retry_review_from_draft_returns_400` (assert `kind` on 400). Add `test_domain_error_handler_returns_kind`. Update failure metadata tests to expect `review_failed` + `kind`.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/application/commands/test_retry_adr_for_review.py tests/infrastructure/api/test_adr_api.py -q`
- `just migrate-backend-test` applies `004_review_failed` cleanly
- `cd backend && uv run ruff check .`
- `cd backend && uv run ty check`

#### Manual Verification:

- `curl -X POST /api/adrs/{id}/retry-review` with session cookie on a `review_failed` ADR returns 202 and subsequent `GET` shows `in_review`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Frontend Error UX

### Overview

Surface `review_failed` status, structured error panel, editor unlock, and retry CTA wired to new endpoint.

### Changes Required:

#### 1. API types and client

**Files**: `frontend/composables/useApi.ts`, `frontend/app/stores/adr.ts`

**Intent**: Type and call retry endpoint.

**Contract**: Extend `ReviewError` type with `kind: string`. Add `retryReview(id: string): Promise<void>` → `POST /adrs/{id}/retry-review`. Store action `retryForReview(id)` reloads ADR and restarts polling (same pattern as `submitForReview`).

#### 2. Status badge

**File**: `frontend/app/components/adr/AdrStatusBadge.vue`

**Intent**: Distinct visual for failure state.

**Contract**: Add `review_failed` entry — label “Review failed”, destructive/red variant (match shadcn destructive palette).

#### 3. Polling composable

**File**: `frontend/app/composables/useAdrReviewPolling.ts`

**Intent**: Polling only for active review, not failure terminal state.

**Contract**: `isReviewPending` remains `status === "in_review" && reviewError === null` (no change needed once backend sets `review_failed`; verify tests still pass).

#### 4. Error panel and actions

**Files**: `frontend/app/components/adr/AdrReviewAnnotations.vue`, `frontend/app/pages/workspace/adr/[id].vue`

**Intent**: Structured error UX with reason, guidance, and retry CTA.

**Contract**:
- Error panel copy projected from `reviewError.kind` — e.g. `retryable_internal_error` → retry guidance; `internal_error` → admin placeholder
- Show “Try again” when `kind === "retryable_internal_error"`
- Button calls `retryForReview`, disables during request, restarts polling
- Update in-review banner copy: only show “being reviewed and cannot be edited” when `status === "in_review"` (not `review_failed`)
- “Publish for review” remains `draft` only; no change to submit button for `review_failed`

#### 5. Persistence guard

**File**: `frontend/app/composables/useAdrPersistence.ts` (if it blocks `in_review` only)

**Intent**: Allow saves in `review_failed`.

**Contract**: Verify save blocked only for `in_review`; adjust if composite `in_review + reviewError` check exists.

#### 6. Frontend tests

**Files**: `frontend/tests/adr-review-annotations.test.ts`, `frontend/tests/adr-editor-page.test.ts`, `frontend/tests/adr.store.test.ts`, `frontend/tests/adr-review-polling.test.ts`

**Intent**: Cover badge, error panel copy, retry CTA visibility, and store retry call.

**Contract**: Add fixtures with `status: "review_failed"` and representative `kind` values. Assert retry button hidden for non-retryable kinds.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run test -- tests/adr-review-annotations.test.ts tests/adr-editor-page.test.ts tests/adr.store.test.ts tests/adr-review-polling.test.ts`
- `cd frontend && pnpm run lint`
- `cd frontend && pnpm run typecheck`

#### Manual Verification:

- Trigger system review failure (mock LLM down in dev) → page shows “Review failed” badge, editable content, error panel with “Try again”
- Click “Try again” → status returns to “In review”, polling resumes
- ADR with non-retryable `kind` shows placeholder admin copy, no retry button

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: PRD & Product Docs

### Overview

Amend PRD to reflect fifth status and updated failure semantics.

### Changes Required:

#### 1. PRD amendment

**File**: `context/foundation/prd.md`

**Intent**: Remove 4-status non-goal; document `review_failed` and retry.

**Contract**:
- Update non-goal line ~173 to allow 5 statuses or remove the 4-status cap
- Update failure behavior ~line 151: system failures → `review_failed` with retry; content/validation issues → `after_review` with ratings
- Add FR or extend FR-005: editing allowed in `review_failed`; retry via dedicated endpoint

#### 2. Test plan alignment

**File**: `context/foundation/test-plan.md`

**Intent**: Close risk #6 (“transitions to an error state”).

**Contract**: Note `review_failed` satisfies risk #6.

### Success Criteria:

#### Automated Verification:

- N/A (docs only)

#### Manual Verification:

- PRD accurately describes the five-status lifecycle and retry flow
- No contradictions between PRD and implemented behavior

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Aggregate: `fail_review` → `review_failed`, `retry_review` guards, rehydrate `AIReviewFailed`
- Handler: infra failures raise/persist `InternalError` (`kind=internal_error`); content issues complete to `after_review`
- Service: merge validation failure returns result (no raise)
- Command: retry emits new submit event, calls `mark_in_review`
- API: global handler returns `kind`; retry endpoint 202/400/404 matrix

### Integration Tests:

- End-to-end: submit → forced LLM failure → `review_failed` → retry → `in_review` → success → `after_review`
- Migration: seeded `in_review` + `review_error` row becomes `review_failed` with backfilled `kind`

### Manual Testing Steps:

1. Create draft ADR, submit for review with LLM unavailable → verify `review_failed` UX
2. Click “Try again” with LLM restored → verify review completes to `after_review` with ratings
3. Verify ADR that previously failed merge validation now lands in `after_review` with annotations
4. Verify workspace list shows “Review failed” badge (no extra list fields)
5. Run migration against DB with a manually seeded stranded row

## Performance Considerations

Negligible — one additional POST endpoint and a JSON field on existing `review_error` column. No new polling paths; `review_failed` is terminal until user retries.

## Migration Notes

- **Projection data migration** (Alembic `004`): auto-transition `in_review` + `review_error` → `review_failed`, backfill `kind`, normalize `code` to `internal_error`
- **Event store**: historical `AIReviewFailed` events lack `kind` — rehydration/projection should default `kind` to `adr_review_failed_error` when missing
- **Rollback**: downgrading migration cannot restore exact pre-migration event-store state; document as projection-only rollback

## References

- Research: `context/changes/error-status/research.md`
- Submit command template: `backend/application/commands/submit_adr_for_review.py`
- Handler failure path: `backend/application/handlers/run_ai_review.py:160-219`
- R-01 validation policy: `context/archive/2026-06-26-adr-validation-re-shape/plan-brief.md`
- Lessons: `context/foundation/lessons.md` (typed `DomainError`, minimal public API)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Domain & Failure Taxonomy

#### Automated

- [x] 1.1 Domain/handler/service tests pass: `uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_adr_rehydrate.py tests/application/handlers/test_run_ai_review.py tests/application/services/test_adr_review_service.py -q` — 2b64a81
- [x] 1.2 Ruff passes: `uv run ruff check .` — 2b64a81
- [x] 1.3 Type check passes: `uv run ty check` — 2b64a81

#### Manual

- [ ] 1.4 N/A — confirm phase 1 automated checks green before Phase 2

### Phase 2: Retry Command, API & Migration

#### Automated

- [x] 2.1 Command and API tests pass: `uv run pytest tests/application/commands/test_retry_adr_for_review.py tests/infrastructure/api/test_adr_api.py -q` — 914fb82
- [x] 2.2 Migration applies: `just migrate-backend-test` — 914fb82
- [x] 2.3 Ruff passes: `uv run ruff check .` — 914fb82
- [x] 2.4 Type check passes: `uv run ty check` — 914fb82

#### Manual

- [ ] 2.5 Global handler returns `kind` on 400; retry endpoint returns 202 and ADR transitions to `in_review` via curl/browser

### Phase 3: Frontend Error UX

#### Automated

- [x] 3.1 Frontend tests pass: `pnpm run test -- tests/adr-review-annotations.test.ts tests/adr-editor-page.test.ts tests/adr.store.test.ts tests/adr-review-polling.test.ts` — c307341
- [x] 3.2 Lint passes: `pnpm run lint` — c307341
- [x] 3.3 Typecheck passes: `pnpm run typecheck` — c307341

#### Manual

- [ ] 3.4 Failed review shows badge, error panel, retry CTA; retry resumes polling

### Phase 4: PRD & Product Docs

#### Automated

- [ ] 4.1 N/A (docs only)

#### Manual

- [ ] 4.2 PRD and test-plan updated; no contradictions with implemented behavior
