# Review Quality Checks Implementation Plan

## Overview

Build F-01: a minimal pytest evaluation harness that grades `ReviewResult` output against golden ADR fixtures for required-section detection and annotation actionability. This is the quality gate contract S-04 must satisfy before AI review annotations are shown to users — not an AI review engine, LLM adapter, or runtime handler.

## Current State Analysis

**Domain (ready):** `ReviewAnnotation`, `ReviewAnnotationKind`, and `ReviewResult` value objects exist in `backend/domain/adr/value_objects.py`. `AIReviewCompleted` carries `ReviewResult` (`backend/domain/adr/events.py`). `InvalidReviewAnnotation` and `InvalidReviewResult` error types exist but have no validators yet. The five-heading starter template is locked in `backend/domain/adr/template.py` and tested in `backend/tests/domain/adr/test_template.py`.

**Persistence (ready, unused for F-01):** `adrs.review_annotations` JSONB column and projection serialization exist from F-02. F-01 does not touch persistence or API layers.

**Missing (all F-01 deliverables):** No markdown section parser, no required-section detector, no empty-vs-missing rules, no actionability validator, no golden fixture set, no grader module, no `backend/tests/review_quality/` directory.

### Key Discoveries:

- F-01 grades the same `ReviewResult` shape S-04 will produce — no separate JSON contract (`research.md`, `value_objects.py:57-71`)
- PRD NFR line 134 mentions "alternatives" but FR-004/FR-010 and the template use `## Options` — follow the five-heading template as canonical
- `test-plan.md` Risk #1: cheapest MVP protection is fixture ADRs + structural checks; probabilistic 80% eval is deferred post-MVP
- Backend test entrypoint is `just test-backend` → `uv run pytest` — no new toolchain
- Domain layer is pure Python with no FastAPI/SQL deps — section parser belongs here per architecture rules

## Desired End State

A developer runs `just test-backend` and a `backend/tests/review_quality/` suite executes deterministic graders against golden ADR fixtures and synthetic `ReviewResult` objects. The harness:

1. Parses ADR markdown and identifies missing or empty required sections (`Context`, `Options`, `Decision`, `Status`, `Consequences`)
2. Grades whether a `ReviewResult` flags the correct sections (precision/recall by section name, not exact LLM wording)
3. Grades whether annotations meet kind-specific actionability rules
4. Reports per-case and aggregate metrics (precision/recall) without a hard 80% CI gate yet

S-04 can import the domain section parser and the test grader module to validate real LLM output before showing annotations to users.

**Verification:** Parser tests pass on all golden fixtures → grader tests pass on hand-crafted good/bad `ReviewResult` pairs → metrics test prints aggregate scores → `uv run ruff check .` and `uv run ty check` pass.

## What We're NOT Doing

- OpenRouter / LLM adapter or any model calls
- `RunAiReview` handler, `submit_adr_for_review` command, or status transitions
- Prompt orchestration, LLM-as-judge, or human calibration
- Inconsistency *quality* grading (only schema/actionability checks for inconsistency annotations)
- Frontend annotation UI
- Persisted harness report artifacts or OpenTelemetry
- Hard CI gate enforcing ≥80% section-gap recall (metrics reported only; threshold gates S-04 integration)
- Configurable section conventions or heading aliases (e.g. `## Alternatives` → `Options`)
- Probabilistic F-score evaluation dataset

## Implementation Approach

Three phases following the domain-first pattern used elsewhere in the backend: pure parser in `domain/adr/`, importable grader in `tests/review_quality/`, then golden fixtures wired into pytest. Synthetic `ReviewResult` objects are hand-crafted in tests — no LLM needed. Grader assertions are structural (section names, field presence), not exact prose.

## Critical Implementation Details

**Placeholder empty rule:** A required heading whose body content (text before the next `##` heading) is blank, whitespace-only, or placeholder-only (`TBD`, `TODO`, `N/A` — case-insensitive match on the trimmed body) counts as empty/missing for grading purposes.

**Heading match rule:** Only exact `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences` headings match (case-sensitive). `## Alternatives` or `# Context` do not count.

**Section name normalization:** Internal section identifiers use title-case names without the `##` prefix (`Context`, `Options`, etc.) for precision/recall matching against annotation `location` or `message` fields.

---

## Phase 1: Domain Section Parser

### Overview

Add pure markdown parsing logic in the domain layer that detects which of the five required ADR sections are missing or empty.

### Changes Required:

#### 1. Required sections module

**File**: `backend/domain/adr/required_sections.py` (new)

**Intent**: Centralize the five-heading contract and parsing logic so both F-01 graders and future S-04 review code share one source of truth.

**Contract**:
- `REQUIRED_SECTION_HEADINGS: tuple[str, ...]` — exact heading strings including `##` prefix, aligned with `ADR_STARTER_TEMPLATE`
- `SectionName` — type alias or enum for normalized names (`Context`, `Options`, `Decision`, `Status`, `Consequences`)
- `ParsedAdrSections` — frozen dataclass mapping each `SectionName` to extracted body text or `None` if heading absent
- `parse_adr_sections(markdown: str) -> ParsedAdrSections` — scan `##` headings, extract body content between headings
- `find_missing_or_empty_sections(markdown: str) -> frozenset[SectionName]` — returns sections that are absent or empty per placeholder rule
- `_is_placeholder_only(text: str) -> bool` — private helper for TBD/TODO/N/A detection

#### 2. Domain package exports

**File**: `backend/domain/adr/__init__.py`

**Intent**: Make parser public API importable as `from domain.adr import find_missing_or_empty_sections, ...`.

**Contract**: Re-export `REQUIRED_SECTION_HEADINGS`, `parse_adr_sections`, `find_missing_or_empty_sections`, and `SectionName`.

#### 3. Domain parser tests

**File**: `backend/tests/domain/adr/test_required_sections.py` (new)

**Intent**: Lock parser behavior independently of the eval harness.

**Contract**: Cover — complete ADR returns empty set; missing single heading detected; empty body detected; placeholder body (`TBD`) detected; multiple gaps; extra non-required sections ignored; wrong synonym `## Alternatives` not counted as `Options`; case mismatch `## context` not matched.

### Success Criteria:

#### Automated Verification:

- Domain parser tests pass: `cd backend && uv run pytest tests/domain/adr/test_required_sections.py`
- Linting passes: `cd backend && uv run ruff check .`
- Type checking passes: `cd backend && uv run ty check`

#### Manual Verification:

- Parser output for `ADR_STARTER_TEMPLATE` alone flags all five sections as empty/missing (template has headings but no body content)
- Review `find_missing_or_empty_sections` output against one complete fixture ADR mentally — all five sections present with real content returns empty set

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Grader Module

### Overview

Build the evaluation grader that scores a `ReviewResult` against a `ReviewQualityCase` — checking required-section annotation coverage, actionability, and basic schema validity.

### Changes Required:

#### 1. Case and verdict dataclasses

**File**: `backend/tests/review_quality/cases.py` (new)

**Intent**: Define the harness input/output contract for fixture-driven grading.

**Contract**:
- `ReviewQualityCase(frozen dataclass)` — fields: `name: str`, `markdown: str`, `expected_missing_sections: frozenset[str]`
- `ReviewQualityVerdict(frozen dataclass)` — fields: `passed: bool`, `missing_section_precision: float`, `missing_section_recall: float`, `failures: tuple[str, ...]`

#### 2. Grader implementation

**File**: `backend/tests/review_quality/grader.py` (new)

**Intent**: Deterministic grading logic S-04 will import to validate review output before user display.

**Contract**:
- `extract_flagged_sections(result: ReviewResult) -> frozenset[str]` — parse `missing_section` annotations to normalized section names from `location` or `message` (structure over exact wording)
- `grade_missing_section_annotations(case: ReviewQualityCase, result: ReviewResult) -> tuple[float, float, tuple[str, ...]]` — compute precision/recall against `case.expected_missing_sections`; return failure messages for false positives/negatives
- `grade_actionability(result: ReviewResult) -> tuple[bool, tuple[str, ...]]` — enforce kind-specific rules:
  - `missing_section`: non-empty `message` and `suggestion` required
  - `conciseness`: non-empty `message`, `suggestion`, and `location` required
  - `inconsistency`: non-empty `message` and `location` required; `suggestion` optional
- `grade_review_output(case: ReviewQualityCase, result: ReviewResult) -> ReviewQualityVerdict` — combine missing-section and actionability grades; `passed` is true only when recall = 1.0, precision = 1.0, and actionability passes

#### 3. Package init

**File**: `backend/tests/review_quality/__init__.py` (new, empty or minimal)

**Intent**: Make `tests.review_quality` a proper Python package for clean imports.

#### 4. Grader unit tests

**File**: `backend/tests/review_quality/test_grader.py` (new)

**Intent**: Verify grader logic with synthetic `ReviewResult` objects — no fixtures files yet.

**Contract**: Cover — perfect match passes; false positive (extra missing_section annotation) fails precision; false negative (missing annotation for gap) fails recall; actionability failures per kind; empty annotations list with expected gaps fails recall; complete ADR with empty annotations passes when no gaps expected.

### Success Criteria:

#### Automated Verification:

- Grader tests pass: `cd backend && uv run pytest tests/review_quality/test_grader.py`
- Linting passes: `cd backend && uv run ruff check .`
- Type checking passes: `cd backend && uv run ty check`

#### Manual Verification:

- Import `grade_review_output` in a Python REPL with a hand-crafted case — verify verdict shape matches expectations

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Fixtures & Harness Tests

### Overview

Add golden ADR markdown fixtures, wire them into end-to-end harness tests, and report aggregate metrics without a hard recall threshold gate.

### Changes Required:

#### 1. Golden fixture files

**Directory**: `backend/tests/review_quality/fixtures/` (new)

**Intent**: Versioned golden ADR inputs with known section presence for deterministic evaluation.

**Contract**: Create markdown files (minimum set):
- `complete.md` — all five sections with substantive content
- `missing_context.md` — no `## Context` heading
- `empty_decision.md` — `## Decision` heading with blank body
- `placeholder_status.md` — `## Status` body is `TBD`
- `missing_multiple_sections.md` — two or more gaps
- `wrong_heading_alternatives.md` — uses `## Alternatives` instead of `## Options` (Options should be flagged missing)
- `extra_sections.md` — includes non-required sections (e.g. `## References`) alongside valid required sections

#### 2. Case registry

**File**: `backend/tests/review_quality/cases.py` (extend)

**Intent**: Load fixtures and define expected missing sections for each case.

**Contract**:
- `FIXTURES_DIR` path constant
- `load_fixture(name: str) -> str` helper
- `ALL_CASES: tuple[ReviewQualityCase, ...]` — one entry per fixture with correct `expected_missing_sections`
- `build_synthetic_result(case: ReviewQualityCase) -> ReviewResult` — helper constructing a passing `ReviewResult` for each case (one `missing_section` annotation per expected gap with valid message/suggestion/location) for harness smoke tests

#### 3. Required-section harness tests

**File**: `backend/tests/review_quality/test_required_sections.py` (new)

**Intent**: End-to-end test that parser ground truth matches fixture expectations and synthetic results pass the grader.

**Contract**:
- For each case in `ALL_CASES`: assert `find_missing_or_empty_sections(case.markdown) == case.expected_missing_sections`
- For each case: assert `grade_review_output(case, build_synthetic_result(case)).passed is True`
- For each case: construct an intentionally incomplete `ReviewResult` (missing one annotation) and assert grader fails

#### 4. Actionability harness tests

**File**: `backend/tests/review_quality/test_annotation_actionability.py` (new)

**Intent**: Verify actionability rules across annotation kinds using synthetic results.

**Contract**: Parametrized tests for each kind — valid annotation passes; missing required field fails with descriptive failure message. Include inconsistency annotations with location+message only (no suggestion).

#### 5. Metrics reporting test

**File**: `backend/tests/review_quality/test_harness_metrics.py` (new)

**Intent**: Aggregate and report precision/recall across all cases without enforcing the PRD 80% NFR threshold in CI.

**Contract**:
- `compute_aggregate_metrics(cases, results) -> dict` helper returning mean precision/recall
- Test runs all cases with synthetic passing results, computes metrics, asserts precision and recall are 1.0 for the golden set
- Test logs or prints aggregate metrics via `caplog` or a simple formatted string — informational only, no `pytest.mark.xfail` on 80% threshold
- Document in test docstring that the ≥80% NFR applies to real LLM output in S-04, not this deterministic golden set

### Success Criteria:

#### Automated Verification:

- Full review quality suite passes: `cd backend && uv run pytest tests/review_quality/`
- Domain parser tests still pass: `cd backend && uv run pytest tests/domain/adr/test_required_sections.py`
- Full backend suite passes: `just test-backend`
- Linting passes: `cd backend && uv run ruff check .`
- Type checking passes: `cd backend && uv run ty check`

#### Manual Verification:

- Scan pytest output for aggregate metrics summary — values are readable and correct for the golden set
- Confirm no LLM calls, DB connections, or API routes were added

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before treating F-01 as complete.

---

## Testing Strategy

### Unit Tests:

- Domain parser: heading extraction, empty detection, placeholder detection, synonym rejection
- Grader: precision/recall math, actionability per kind, verdict aggregation
- Synthetic `ReviewResult` construction — no external dependencies

### Integration Tests:

- Fixture file loading → case registry → parser ground truth alignment
- End-to-end: fixture markdown + synthetic passing result → grader pass
- End-to-end: fixture markdown + deliberately bad result → grader fail with actionable failure messages

### Manual Testing Steps:

1. Run `just test-backend` and confirm all `tests/review_quality/` tests pass
2. Inspect metrics test output for aggregate precision/recall report
3. Optionally construct a `ReviewResult` in REPL and run `grade_review_output` against a case from `ALL_CASES`

## Performance Considerations

All operations are in-memory string parsing on small markdown documents. No performance budget concerns at MVP scale. Parser and grader run in milliseconds per fixture.

## Migration Notes

Not applicable — no schema changes, no data migration. Pure additive code under `domain/adr/` and `tests/review_quality/`.

## References

- Research: `context/changes/review-quality-checks/research.md`
- Harness practices: `context/changes/review-quality-checks/harness-good-practices.md`
- PRD guardrails: `context/foundation/prd.md:110-115`, `134-135`, `143-149`
- Test plan Risk #1: `context/foundation/test-plan.md:42-54`
- Domain value objects: `backend/domain/adr/value_objects.py:51-71`
- Starter template: `backend/domain/adr/template.py:3-5`
- S-04 integration path: `context/foundation/application-architecture.md:157-167`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Domain Section Parser

#### Automated

- [x] 1.1 Domain parser tests pass: `cd backend && uv run pytest tests/domain/adr/test_required_sections.py`
- [x] 1.2 Linting passes: `cd backend && uv run ruff check .`
- [x] 1.3 Type checking passes: `cd backend && uv run ty check`

#### Manual

- [x] 1.4 Parser output for starter template and one complete fixture verified manually

### Phase 2: Grader Module

#### Automated

- [x] 2.1 Grader tests pass: `cd backend && uv run pytest tests/review_quality/test_grader.py`
- [x] 2.2 Linting passes: `cd backend && uv run ruff check .`
- [x] 2.3 Type checking passes: `cd backend && uv run ty check`

#### Manual

- [ ] 2.4 `grade_review_output` verified in REPL with hand-crafted case

### Phase 3: Fixtures & Harness Tests

#### Automated

- [ ] 3.1 Full review quality suite passes: `cd backend && uv run pytest tests/review_quality/`
- [ ] 3.2 Domain parser tests still pass: `cd backend && uv run pytest tests/domain/adr/test_required_sections.py`
- [ ] 3.3 Full backend suite passes: `just test-backend`
- [ ] 3.4 Linting passes: `cd backend && uv run ruff check .`
- [ ] 3.5 Type checking passes: `cd backend && uv run ty check`

#### Manual

- [ ] 3.6 Aggregate metrics output reviewed; confirm no LLM/DB/API additions
