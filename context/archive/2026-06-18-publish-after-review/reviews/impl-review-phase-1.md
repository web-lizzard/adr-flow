<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Publish After Review — Phase 1

- **Plan**: context/changes/publish-after-review/plan.md
- **Scope**: Phase 1 of 2
- **Date**: 2026-06-18
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Unplanned mark_in_review_if_draft in projection port/adapter

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Scope Discipline
- **Location**: backend/application/ports/adr_projection.py:19, projections/adr_projection.py:59
- **Detail**: Phase 1 plan only called for mark_proposed. mark_in_review_if_draft was added to port, adapter, and fakes with zero production callers.
- **Fix A ⭐ Recommended**: Remove mark_in_review_if_draft from this change set.
- **Decision**: FIXED via Fix A — removed from port, adapter, fakes; reverted projection-review test to mark_in_review.

### F2 — Unrelated files in working tree

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: AGENTS.md, .devcontainer/docker-compose.yml, backend/domain/adr/required_sections.py
- **Detail**: Same uncommitted tree mixes Phase 1 publish with Ollama devcontainer, AGENTS.md docs, required_sections fix.
- **Fix**: Revert or stash unrelated files before commit.
- **Decision**: SKIPPED

### F3 — TOCTOU status guard on publish

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/application/commands/publish_adr.py:70, projections/adr_projection.py:49
- **Detail**: Status checked outside transaction; mark_proposed had no WHERE status guard.
- **Fix A ⭐ Recommended**: Conditional mark_proposed with WHERE status='after_review' + rowcount check.
- **Decision**: FIXED via Fix A — mark_proposed returns bool; handler raises AdrInvalidPublishStatus if not transitioned.

### F4 — Manual verification pending (Progress 1.7, 1.8)

- **Severity**: 👁️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/publish-after-review/plan.md:343-344
- **Detail**: Manual API checks not yet confirmed; checkboxes unchecked per plan pause note.
- **Fix**: Run manual curl/httpx verification before Phase 2.
- **Decision**: SKIPPED

### F5 — Extra event-store tests beyond plan

- **Severity**: 👁️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/tests/infrastructure/adapters/persistence/test_event_store.py
- **Detail**: Additional sync-projection and legacy-payload tests beyond ADRPublished skip case; benign.
- **Fix**: No action needed.
- **Decision**: SKIPPED

### F6 — Unused db_engine fixture in API test

- **Severity**: 👁️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/infrastructure/api/test_adr_api.py:686
- **Detail**: test_publish_rejects_non_after_review_status declares unused db_engine fixture.
- **Fix**: Remove unused parameter.
- **Decision**: SKIPPED
