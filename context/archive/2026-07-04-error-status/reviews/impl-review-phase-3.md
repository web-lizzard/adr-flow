<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Error Status — Phase 3

- **Plan**: context/changes/error-status/plan.md
- **Scope**: Phase 3 of 4
- **Date**: 2026-07-05
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Retry API errors invisible on review_failed page

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/pages/workspace/adr/[id].vue:213,269-271
- **Detail**: `onRetryForReview` sets `submitError` on failure, but that ref is only rendered inside `v-if="showSubmitButton"` (draft-only). On `review_failed`, retry API errors are swallowed in the UI.
- **Fix**: Add a `retryError` ref (or surface errors in the review panel) and render it when `showReviewPanel` is true.
  - Strength: Matches submit/publish error surfacing; user sees why retry failed.
  - Tradeoff: One extra ref and template block.
  - Confidence: HIGH — submit/publish already follow this pattern.
  - Blind spot: None significant.
- **Decision**: FIXED

### F2 — isRetrying not wired into editor/save guards

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/app/pages/workspace/adr/[id].vue:26-31,101
- **Detail**: `isEditorDisabled` and `isBlockingSave` include `isSubmitting` / `isPublishing` but not `isRetrying`. Editor and blur-save remain active during retry despite plan "disables during request" (button disables, but not editor).
- **Fix**: Add `isRetrying` to both `isEditorDisabled` and `isBlockingSave` computeds.
- **Decision**: FIXED

### F3 — Retry does not save dirty edits before API call

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/pages/workspace/adr/[id].vue:204-216
- **Detail**: `onRetryForReview` does not save dirty edits before retry; `onSubmitForReview` / `onPublish` do (`save` if `isDirty`). User can edit in `review_failed`, click "Try again" without blur, and retry stale server content.
- **Fix**: Mirror submit pattern: `if (adr.isDirty.value) await adr.save()` before `retryForReview`.
  - Strength: Aligns with submit/publish; ensures retry uses latest content.
  - Tradeoff: Adds latency before retry; save failure must be handled.
  - Confidence: HIGH — identical pattern exists on submit.
  - Blind spot: None significant.
- **Decision**: FIXED

### F4 — Legacy kind adr_review_failed_error unmapped in error panel

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/app/components/adr/AdrReviewAnnotations.vue:28-32,55-64
- **Detail**: Guidance and retry CTA only map `retryable_internal_error` and `internal_error`. Unknown kinds (e.g. `adr_review_failed_error` in event defaults and test fixtures) show message only — no guidance, no retry button. New failures use `retryable_internal_error`; legacy/rehydrated rows may not.
- **Fix**: Map `adr_review_failed_error` to the same copy/CTA as `retryable_internal_error`, or normalize kinds in the API layer.
- **Decision**: FIXED

### F5 — API function named retryAdrForReview vs plan retryReview

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/composables/useApi.ts:118-121
- **Detail**: Plan specifies `retryReview(id)`; implementation uses `retryAdrForReview` matching `submitAdrForReview` convention. Store action `retryForReview` matches plan.
- **Fix**: No code change needed — naming follows existing API client convention.
- **Decision**: SKIPPED (accepted — matches submitAdrForReview convention)
