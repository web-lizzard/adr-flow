<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: ADR History Cards Implementation Plan

- **Plan**: `context/changes/adr-history-cards/plan.md`
- **Scope**: Phases 2-4 of 4
- **Date**: 2026-06-17
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | FAIL |

## Findings

### F1 - Unplanned test-runtime and dependency surface changes

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: `frontend/vitest.config.ts:1`, `frontend/tests/setup.ts:1`, `frontend/package.json:42`, `frontend/pnpm-lock.yaml`
- **Detail**: Phases 2-4 planned UI/state/component work, but implementation also changed test runtime config and dependencies (`jsdom`, `@vitejs/plugin-vue`) plus lockfile. These are plausibly needed for added component/page tests, but they expand scope beyond the listed phase contracts.
- **Fix A ⭐ Recommended**: Record these as an explicit plan addendum for Phases 3-4 test support.
  - Strength: Preserves useful work and aligns source-of-truth scope with actual implementation.
  - Tradeoff: Broadens scope after the fact.
  - Confidence: HIGH — the extra files are tightly connected to newly added ADR component/page tests.
  - Blind spot: Does not prove every added dependency is strictly minimal.
- **Fix B**: Revert infra/dependency changes and move expanded testing to a follow-up change.
  - Strength: Keeps strict phase scope boundaries.
  - Tradeoff: Loses immediate test coverage for new component/page behavior.
  - Confidence: MEDIUM — may break newly introduced tests until follow-up lands.
  - Blind spot: Not fully verified which tests depend on each config/dependency delta.
- **Decision**: SKIPPED

### F2 - Automated frontend verification is currently blocked by Node/pnpm mismatch

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: N/A (tooling runtime)
- **Detail**: Re-running all Phase 2-4 frontend verification commands failed before execution with `ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite`, while `pnpm` reported requiring Node `>=22.13` and environment reported Node `v20.18.2`. This blocks objective re-validation of the automated criteria for these phases.
- **Fix**: Use a Node runtime compatible with the installed pnpm (>=22.13), then rerun all Phase 2-4 frontend verification commands and record outcomes.
  - Strength: Restores deterministic verification gate for this change.
  - Tradeoff: Requires environment/toolchain alignment step.
  - Confidence: HIGH — failure occurs before project code runs and is clearly version-gated.
  - Blind spot: Does not guarantee test success after runtime alignment.
- **Decision**: SKIPPED (user opted to proceed without this fix)

### F3 - ADR status contracts remain loosely typed as string

- **Severity**: 👀 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `frontend/app/stores/adr.ts:15`, `frontend/app/stores/adr.ts:23`, `frontend/app/components/adr/AdrStatusBadge.vue:5`, `frontend/app/pages/workspace/adr/[id].vue:15`
- **Detail**: Status-driven behavior (read-only gating and badge mapping) depends on literal values, but status remains typed as plain `string` in frontend contracts. This is not breaking now, but weakens compile-time protection against typo or enum drift.
- **Fix**: Introduce a shared `AdrStatus` union type and consume it in store/component/page props.
- **Decision**: SKIPPED
