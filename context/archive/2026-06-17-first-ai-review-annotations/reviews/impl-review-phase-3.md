<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: First AI Review Annotations — Phase 3

- **Plan**: context/changes/first-ai-review-annotations/plan.md
- **Scope**: Phase 3 of 4
- **Date**: 2026-06-18
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 7 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Findings

### F1 — Unhandled poll errors during review status refresh

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/composables/useAdrReviewPolling.ts:27
- **Detail**: `refreshReviewStatus` is awaited inside the interval callback without try/catch. Network or auth failures become unhandled rejections and polling continues silently with stale status.
- **Fix**: Wrap the poll tick in try/catch; after N consecutive failures, stop polling and surface recoverable feedback on the editor page.
  - Strength: Prevents silent stuck UI when review-status endpoint fails transiently.
  - Tradeoff: Requires a small error state on the page or composable return value.
  - Confidence: HIGH — standard async interval hygiene.
  - Blind spot: None significant.
- **Decision**: FIXED

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/pages/workspace/adr/[id].vue:38-40
- **Detail**: `onMounted` calls `adr.load(adrId.value)` with no try/catch or error UI. A 404 or network failure leaves a blank editor with no feedback.
- **Fix**: Add `loadError` ref, catch load failures, and show a message with a back link (mirror `listError` on the workspace page).
- **Decision**: FIXED

### F3 — Poll ticks can overlap

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/app/composables/useAdrReviewPolling.ts:17-27
- **Detail**: `useIntervalFn` does not wait for the prior async tick. Slow `refreshReviewStatus` responses can stack concurrent polls.
- **Fix**: Guard with an `inFlight` boolean; skip starting a new tick while the previous one is running.
- **Decision**: FIXED

### F4 — Persistence can race during submit transition

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/composables/useAdrPersistence.ts:22-24, frontend/app/pages/workspace/adr/[id].vue:82-101
- **Detail**: `isReviewEditable` keys off client `status !== "in_review"`. During submit, the client may still show `draft` while the server is already `in_review`, so blur/beacon saves can fire and be rejected. Inputs are not disabled while `isSubmitting`.
- **Fix A ⭐ Recommended**: Pass `isSubmitting` into persistence (or a shared "review transition" flag) and suppress blur/beacon while true; disable editor inputs when `isSubmitting`.
  - Strength: Closes the race without changing server contracts.
  - Tradeoff: Slightly more props/wiring between page and persistence composable.
  - Confidence: HIGH — aligns with existing `isReadOnly` gating.
  - Blind spot: Very fast submit may still race before flag is set.
- **Fix B**: Rely on server 400 on save during `in_review` and swallow errors in beacon path
  - Strength: No frontend wiring changes.
  - Tradeoff: Accepts failed save attempts and possible user confusion.
  - Confidence: MEDIUM — errors are swallowed today.
  - Blind spot: User may lose unsaved edits if beacon fires at wrong moment.
- **Decision**: FIXED via Fix A

### F5 — useAdr composable omits review-field wrappers

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/app/composables/useAdr.ts:1-21
- **Detail**: Plan requires re-exporting review fields through computed wrappers. Implementation only passes through `submitForReview` and `refreshReviewStatus`; consumers read `currentAdr.reviewAnnotations` etc. directly.
- **Fix A ⭐ Recommended**: Add `reviewAnnotations`, `reviewedAt`, `reviewError` computeds derived from `store.currentAdr`.
  - Strength: Matches plan contract and keeps page templates cleaner.
  - Tradeoff: Thin wrappers; minor API surface growth.
  - Confidence: HIGH.
  - Blind spot: None significant.
- **Fix B**: Update plan to document that review fields are accessed via `currentAdr`
  - Strength: No code change.
  - Tradeoff: Plan drift remains; less ergonomic API.
  - Confidence: HIGH.
  - Blind spot: Future pages may bypass the composable inconsistently.
- **Decision**: FIXED via Fix A

### F6 — Review panel visibility broader than plan

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/app/pages/workspace/adr/[id].vue:23-33
- **Detail**: Plan says show panel when annotations or review error exist. `showReviewPanel` also returns true for all `after_review` ADRs (including zero annotations) to support the component empty state.
- **Fix A ⭐ Recommended**: Document in plan as intentional — empty-state panel for clean `after_review` UX.
  - Strength: Preserves implemented UX; updates source of truth.
  - Tradeoff: Plan becomes slightly moving target.
  - Confidence: HIGH.
  - Blind spot: None significant.
- **Fix B**: Tighten `showReviewPanel` to annotations-or-error only
  - Strength: Strict plan adherence.
  - Tradeoff: Users with zero annotations see no feedback panel after review.
  - Confidence: HIGH.
  - Blind spot: Product may want the empty state.
- **Decision**: FIXED via Fix A (plan addendum)

### F7 — Duplicated error message helper

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/app/pages/workspace/adr/[id].vue:104-112
- **Detail**: Local `getAdrErrorMessage` duplicates `getAuthErrorMessage` from `frontend/app/stores/auth.ts`, used on login/register/workspace pages.
- **Fix**: Import `getAuthErrorMessage` from `@/stores/auth` and remove the local copy.
- **Decision**: FIXED (resolved while fixing F2)

### F8 — No watch on route param id

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/app/pages/workspace/adr/[id].vue:38-40
- **Detail**: If Nuxt reuses the component when navigating between `/workspace/adr/:id` routes, stale ADR data may display until manual refresh.
- **Fix**: `watch(adrId, (id) => adr.load(id))` or key the page on `adrId`.
- **Decision**: FIXED

### F9 — Extra polling test file (benign)

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/tests/adr-review-polling.test.ts
- **Detail**: Not listed in Phase 3 plan file list but adds valuable coverage for polling start/stop on error.
- **Fix**: No action required; optional plan addendum.
- **Decision**: SKIPPED

### F10 — Manual verification items still pending

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: context/changes/first-ai-review-annotations/plan.md (3.6–3.10)
- **Detail**: Phase 3 automated checks are marked complete in Progress; manual items 3.6–3.10 remain unchecked. Review agent could not re-run automated commands in this environment (Node/pnpm toolchain mismatch); trust plan markers with caveat.
- **Fix**: Complete manual browser verification before treating Phase 3 done.
- **Decision**: SKIPPED (manual verification deferred to human)
