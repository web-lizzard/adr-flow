<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: ADR Validation Reshape

- **Plan**: context/changes/adr-validation-re-shape/plan.md
- **Scope**: Full plan (Phases 1–5)
- **Date**: 2026-07-04
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Application layer imports infrastructure utility

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture
- **Location**: backend/application/services/adr_review_service.py:31
- **Detail**: `from infrastructure.llm.rate_limit import retry_delay_seconds` was the only import from infrastructure/ in the application/ layer, violating hexagonal boundary.
- **Fix**: Created `application/ports/retry_delay.py` with `RetryDelayPort` Protocol and default `ExponentialBackoff`. Infrastructure adapter `LlmRetryDelay` wraps the rate-limit-aware logic. Factory injects the adapter.
- **Decision**: FIXED

### F2 — rate_limit.py naming vs explicit scope exclusion

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/infrastructure/llm/rate_limit.py
- **Detail**: Plan says "NOT doing: rate limiting" but adds `rate_limit.py`. Actual functionality is retry-delay calculation (exponential backoff + provider reset-header awareness), not request throttling. Naming creates confusion.
- **Fix**: Rename to `retry_delay.py` to accurately reflect purpose.
- **Decision**: SKIPPED

### F3 — Unplanned AdrReviewSidebar.vue

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW
- **Dimension**: Scope Discipline
- **Location**: frontend/app/components/adr/AdrReviewSidebar.vue
- **Detail**: New sidebar wrapper component not in plan. Benign UX improvement — structural, not cosmetic.
- **Decision**: SKIPPED

### F4 — _fail_review always uses code "validation_failed"

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW
- **Dimension**: Plan Adherence
- **Location**: backend/application/handlers/run_ai_review.py:167
- **Detail**: All failure reasons (LLM timeouts, provider errors, validation failures) share code `validation_failed`. Plan left the choice open and code is internally consistent.
- **Decision**: SKIPPED

## Automated Verification Results

| Command | Result |
|---------|--------|
| `uv run ruff check . && uv run ty check` | PASS |
| `uv run pytest tests/domain/adr/ -q` | 66 passed |
| `uv run pytest tests/application/ -q` | 47 passed |
| `uv run pytest tests/review_quality/ -q` | 52 passed, 2 skipped |
| `uv run pytest` (full) | 330 passed, 2 skipped |
| `pnpm run typecheck && pnpm run lint` | PASS |
| `pnpm run test -- adr-review-annotations adr-editor-page` | 56 passed |
| `pre-commit run --all-files` | PASS |
