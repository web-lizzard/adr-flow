<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Command Handlers — Aggregate Source of Truth

- **Plan**: context/changes/command-handlers-aggregate-source-of-truth/plan.md
- **Scope**: Phase 1–3 of 3
- **Date**: 2026-06-19
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Aggregate imports events (plan said it must not)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Plan Adherence
- **Location**: backend/domain/adr/aggregate.py:9-17
- **Detail**: The plan explicitly stated "aggregate.py does NOT import from domain/adr/events.py" and "rehydrate.py is the event-type dispatch boundary." Instead, ADR.restore (lines 81–148) pattern-matches all 7 event types directly, and rehydrate.py is a thin wrapper. Root cause: the "Keep class public API minimal" lesson required _-prefixed transition helpers, making an external rehydrator impossible.
- **Fix A ⭐ Recommended**: Document as a plan addendum
  - Strength: Design is internally consistent; restore is a classmethod factory that never leaks events into instance methods.
  - Tradeoff: Plan becomes a living document with post-hoc rationale.
  - Confidence: HIGH.
  - Blind spot: Future maintainers may not realize restore was intentionally colocated.
- **Fix B**: Extract restore back to rehydrate.py
  - Strength: Matches original architectural intent.
  - Tradeoff: Requires making transition helpers non-private, contradicting lessons-learned rule.
  - Confidence: LOW.
  - Blind spot: Would need to update multiple test files.
- **Decision**: FIXED via Fix A — documented as plan addendum A1.

### F2 — Discarded aggregate return values (pattern inconsistency)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/application/commands/publish_adr.py:48, backend/application/handlers/run_ai_review.py:175,229
- **Detail**: ADR is a frozen dataclass — command methods return a new instance. Three call sites discarded the return value while other handlers consistently capture it.
- **Fix**: Capture return values for consistency with sibling handlers.
- **Decision**: FIXED — assigned to `new_adr` with noqa for unused-variable lint in handler.

### F3 — aggregate_type naming inconsistency ("adr" vs "User")

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/application/commands/register_user.py:73
- **Detail**: ADR commands use aggregate_type="adr" (lowercase) while user command used "User" (PascalCase). load_stream queries must match exactly.
- **Fix**: Normalize to lowercase "user"; make load_stream case-insensitive for backward compat with existing DB records.
- **Decision**: FIXED + ACCEPTED-AS-RULE: Normalize aggregate_type strings to lowercase

## Automated Verification

- `pytest` — 273 passed, 2 skipped ✅
- `ruff check .` — all checks passed ✅
- `ty check` — all checks passed ✅
- `pre-commit run --all-files` — all hooks passed ✅
