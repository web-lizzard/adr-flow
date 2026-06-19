<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Command Handlers — Aggregate Source of Truth (Phase 2)

- **Plan**: context/changes/command-handlers-aggregate-source-of-truth/plan.md
- **Scope**: Phase 2 of 3
- **Date**: 2026-06-19
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Unplanned `required_sections.py` change

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: backend/domain/adr/required_sections.py:63
- **Detail**: Phase 2 plan lists no domain changes. Working tree removes `.rstrip()` from heading lookup (`line.rstrip()` → `line`). Unrelated to UoW locking or command handler refactor; may affect ADR section parsing behavior.
- **Fix A ⭐ Recommended**: Revert `required_sections.py` change; land separately if intentional.
  - Strength: Keeps Phase 2 diff focused on planned scope.
  - Tradeoff: If the `.rstrip()` removal fixes a real bug, it waits for a follow-up PR.
  - Confidence: HIGH — change is one line and clearly orthogonal to Phase 2.
  - Blind spot: Haven't verified whether the change fixes a failing test or production bug.
- **Fix B**: Document as plan addendum and keep in this change set.
  - Strength: Preserves work if the fix is needed now.
  - Tradeoff: Blurs Phase 2 scope; reviewers must reason about parsing semantics in a handler-refactor PR.
  - Confidence: MEDIUM — depends on whether the change was deliberate.
  -   Blind spot: No test added for the heading behavior change.
- **Decision**: SKIPPED

### F2 — Publish log uses post-transition status

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/application/commands/publish_adr.py:67
- **Detail**: When `mark_proposed` returns false (defense-in-depth), log field `current_status=new_adr.status.value` reflects aggregate state after `adr.publish()` (`proposed`), not the pre-transition or projection status. Misleading for diagnosing projection/aggregate drift.
- **Fix**: Log `adr.status.value` (pre-transition) or a dedicated `projection_status` field instead of `new_adr.status.value`.
- **Decision**: FIXED

### F3 — Missing ownership-guard tests for submit and publish

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/application/commands/test_submit_adr_for_review.py, test_publish_adr.py
- **Detail**: Handlers implement ownership guard (`adr.user_id.value != command.user_id` → `AdrNotFound`). `test_update_adr_content.py` has `test_update_adr_content_raises_not_found_when_owner_mismatch`; submit and publish lack equivalent tests.
- **Fix**: Add owner-mismatch tests mirroring the update handler test pattern.
- **Decision**: SKIPPED

### F4 — Manual verification items still pending

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: plan.md Progress 2.5, 2.6
- **Detail**: Automated checks (2.1–2.4) pass. Manual items 2.5 (duplicate title without repository pre-read) and 2.6 (duplicate email without pre-read) remain unchecked. Code review confirms handlers no longer call `find_by_title_for_owner` or email pre-read; integration coverage exists in `test_unit_of_work.py` for constraint mapping.
- **Fix**: Complete manual verification and check off 2.5/2.6 in plan Progress.
- **Decision**: SKIPPED
