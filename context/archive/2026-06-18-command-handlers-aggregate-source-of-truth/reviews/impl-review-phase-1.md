<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Command Handlers — Aggregate Source of Truth (Phase 1)

- **Plan**: context/changes/command-handlers-aggregate-source-of-truth/plan.md
- **Scope**: Phase 1 of 3
- **Date**: 2026-06-19
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical (2 skipped) [2 warnings] [2 observations]

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | FAIL |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | FAIL |

## Findings

### F1 — Missing imports for typed domain errors

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: application/commands/submit_adr_for_review.py:65, update_adr_content.py:53, tests/domain/test_adr_errors.py, tests/application/commands/test_*.py
- **Detail**: Phase 2 command handlers and tests raise/assert `AdrInvalidSubmitStatus` and `AdrEditWhileInReview` without importing them. `ty check` reports 8 unresolved references; runtime `NameError` on those paths.
- **Fix**: Add `AdrInvalidSubmitStatus` and `AdrEditWhileInReview` to `from domain.errors import …` in all four affected files.
- **Decision**: SKIPPED

### F2 — Phase 2 command handler edits in Phase 1 working tree

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Scope Discipline
- **Location**: application/commands/submit_adr_for_review.py, update_adr_content.py, create_adr.py
- **Detail**: Three command handlers partially modified but still load projection read models — Phase 2 work mixed into Phase 1 diff; introduced F1 breakage.
- **Fix A ⭐ Recommended**: Revert command handler and command-test changes; keep Phase 1 domain/event-store files only.
- **Fix B**: Keep handler edits and finish Phase 2 early.
- **Decision**: SKIPPED

### F3 — update_content API split from plan

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: domain/adr/aggregate.py:70-100
- **Detail**: Plan specified single `update_content(title, content, updated_at)`; implementation splits into `update_content` / `update_title`. Rehydrator handles optional title on `ADRContentUpdated` — semantically sound.
- **Fix**: Update plan Phase 1 contract to document split API.
- **Decision**: FIXED — plan.md updated

### F4 — aggregate_type casing inconsistency in EventStore tests

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: tests/infrastructure/adapters/persistence/test_event_store.py:59, 215
- **Detail**: Some append calls used `aggregate_type="ADR"` while production and `load_stream` tests use `"adr"`.
- **Fix**: Change test append calls to `aggregate_type="adr"`.
- **Decision**: FIXED

### F5 — EventStore load_stream deserialization coverage partial

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: tests/infrastructure/adapters/persistence/test_event_store.py
- **Detail**: Plan calls for all registered event types; tests cover ordering, empty stream, and two ADR event types only.
- **Fix**: Add parametrized round-trip tests per `_EVENT_TYPES` type (or defer to Phase 3).
- **Decision**: SKIPPED

### F6 — No is_deleted guards on ADR command methods

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: domain/adr/aggregate.py:70-92
- **Detail**: Command methods do not reject operations on soft-deleted ADRs. Phase 2 stream-load path will call these after replay including `ADRSoftDeleted`.
- **Fix**: Add `is_deleted` invariant checks with dedicated `DomainError` subclass before Phase 2.
- **Decision**: SKIPPED
