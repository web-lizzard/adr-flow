<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Error Status

- **Plan**: context/changes/error-status/plan.md
- **Scope**: Phases 1–2 of 4
- **Date**: 2026-07-05
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — 5xx error messages leaked to API clients

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/infrastructure/api/exception_handlers.py:24-30
- **Detail**: The global handler returns `exc.message` verbatim for all status codes, including 500 (InternalError) and 502 (RetryableInternalError). These messages originate from caught exceptions in the review pipeline and may expose internal implementation details to API clients.
- **Fix A ⭐ Recommended**: Redact 5xx messages — return a generic "An internal error occurred" for status_code >= 500 and log the real message server-side.
  - Strength: One conditional in `domain_error_handler`; standard practice.
  - Tradeoff: Frontend loses diagnostic detail in dev; mitigated by structured logs.
  - Confidence: HIGH — no callers depend on the 5xx message text.
  - Blind spot: None significant.
- **Fix B**: Return message only in non-production environments
  - Strength: Preserves dev ergonomics.
  - Tradeoff: Requires env-aware logic in the handler; risk of forgetting to toggle.
  - Confidence: MEDIUM — adds conditional complexity.
  - Blind spot: Env detection must be reliable.
- **Decision**: FIXED (Fix A)

### F2 — _with_review_failed does not update updated_at

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/domain/adr/aggregate.py:221-227
- **Detail**: `_with_review_failed` sets `status` and `review_error` but does not update `updated_at`. The projection layer writes a fresh `updated_at` via `failed_at`, but the in-memory aggregate retains the stale timestamp. Compare with `_with_submitted_for_review` (line 196) and `_with_published` (line 229) — both accept and set `updated_at`.
- **Fix**: Add `updated_at` parameter to `_with_review_failed` and pass `datetime.now(UTC)` from the handler into `fail_review`.
  - Strength: Aligns with the established pattern in every other transition method.
  - Tradeoff: Minor signature change on `fail_review`.
  - Confidence: HIGH — mirrors existing transition methods.
  - Blind spot: None significant.
- **Decision**: FIXED

### F3 — Per-route exception handlers not replaced by global handler

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/infrastructure/api/routers/adr.py:85-92, 116-123, 143-149
- **Detail**: Plan Phase 2.1 says to replace duplicated per-route `except DomainError` blocks. The global handler is registered but every route still catches AdrNotFound locally and raises HTTPException manually. The retry endpoint copies the same pattern from submit.
- **Fix**: Remove local `except AdrNotFound` blocks and let the global handler catch them.
  - Strength: Removes ~40 lines of duplicated try/except/log boilerplate; `kind` appears in all 404 responses automatically.
  - Tradeoff: Per-route structured log lines (e.g. `route.adrs.retry_review.rejected`) are lost.
  - Confidence: MEDIUM — the logging tradeoff needs a decision.
  - Blind spot: Per-route log messages may be relied on for observability.
- **Decision**: FIXED

### F4 — Migration maps legacy validation_failed to adr_review_failed_error

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/infrastructure/adapters/persistence/migrations/versions/004_review_failed_status.py:31-35
- **Detail**: Plan says to normalize legacy `code` from `validation_failed` to `internal_error` for migrated rows. The migration maps unknown codes (including `validation_failed`) to `adr_review_failed_error` instead. This means the frontend will interpret legacy failures as retryable rather than non-retryable.
- **Fix**: Update the ELSE branch to `'internal_error'`.
  - Strength: Matches the plan's rationale — legacy failures were system errors mislabeled as validation failures.
  - Tradeoff: If any legacy rows were genuinely retryable, they'd be marked non-retryable.
  - Confidence: MEDIUM — depends on what legacy `validation_failed` rows represent.
  - Blind spot: No way to distinguish retryable vs non-retryable in legacy data.
- **Decision**: FIXED

### F5 — code→kind rename pulled from Phase 2 into Phase 1

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/domain/adr/value_objects.py, events.py, aggregate.py
- **Detail**: Plan says Phase 1 keeps ReviewError as `code` + `message` and Phase 2 introduces `kind`. Implementation renamed `code` to `kind` everywhere in Phase 1. This is a design improvement (avoids a breaking rename between phases) and is functionally correct.
- **Fix**: No code change needed — update the plan to reflect the actual approach.
- **Decision**: SKIPPED

### F6 — ExceptionGroup handling drops sibling exceptions

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/application/services/adr_review_service.py:89-95
- **Detail**: When TaskGroup raises an ExceptionGroup containing multiple errors, only the first matching RetryableInternalError or InternalError is re-raised. Other exceptions in the group are silently dropped. The review still fails correctly, but diagnostic context about which sections failed is lost.
- **Fix**: Log the full ExceptionGroup before re-raising the first application-level error.
- **Decision**: SKIPPED
