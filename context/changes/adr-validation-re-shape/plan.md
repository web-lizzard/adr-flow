# ADR Validation Reshape — Implementation Plan

## Overview

Replace the monolithic single-LLM review with a three-phase pipeline: **static pre-LLM gap detection**, **parallel per-section LLM scoring (0–5) plus a cross-section inconsistency call**, and **strict merge validation**. Partial failures fail the review (`_fail_review`); per-call LLM retries are configurable (default 2). Expose `section_ratings` through API and a minimal frontend panel. Close S-07 as superseded and update the PRD to match the new output model.

## Current State Analysis

Today `AdrReviewService.review_adr` makes one `complete_structured(ReviewPayload)` call for the full document (`backend/application/services/adr_review_service.py:18-39`). `RunAiReviewHandler` retries up to twice and, after exhausted retries, still completes with the last LLM output when validation fails (`backend/application/handlers/run_ai_review.py:130-137`) — partial S-07 landing. `validate_review_result` cross-checks parser gaps against LLM `missing_section` annotations (`backend/application/review_quality.py:85-101`). Static parsing already exists in `required_sections.py` but runs only post-LLM and in the fake LLM.

## Desired End State

When a user publishes for review:

1. **Phase 0 (static)** — `find_missing_or_empty_sections` emits deterministic `missing_section` annotations and `section_ratings` with score `0` for gap sections; no LLM call for those sections.
2. **Phase 1 (parallel LLM)** — up to six concurrent calls: five section-scoped rating calls for present sections, one cross-section Decision↔Status inconsistency call. Each call retries up to `REVIEW_LLM_ATTEMPTS_PER_CALL` (default 2) before the whole review fails.
3. **Phase 2 (merge + validate)** — merge into one `ReviewResult` with `annotations` (static + LLM) and `section_ratings` (all five sections). Post-merge validation checks actionability and rating schema. Any failure raises → handler `_fail_review`.
4. **Delivery** — on success, `AIReviewCompleted` persists full `ReviewResult` (JSONB, no migration). API returns `section_ratings`; frontend shows ratings below existing annotation groups.

### Key Discoveries

- `ParsedAdrSections.body_for()` is ready for per-section prompts (`required_sections.py:39-46`).
- `ReviewResult` persistence is JSONB dump — optional `section_ratings` needs no column migration (`adr_projection.py`).
- Fake LLM already mirrors static gap detection — should move to service layer (`fake_completion.py:28-37`).
- S-07 (`review-validation-logs-only`) is `implementing` but superseded by this slice's strict-failure model.

## What We're NOT Doing

- Conditional re-review eligibility (S-09) — separate slice
- Handler-level full-review retry loop — deferred; per-call retries only for now
- Post-merge validation failure recovery / resubmit UX — later slice
- Polished ratings UI / re-style — minimal list below annotations only
- Cost controls, rate limiting, or latency budgets
- Rubric calibration harness with golden expected scores (follow-up if needed)
- PRD FR-008 "exactly once" re-review exception (S-09)
- Finishing S-07 Phase 2–3 (handler tests for logs-only path)

## Implementation Approach

Promote the existing parser to Phase 0, split prompts and wire schemas by section, orchestrate parallel calls inside `AdrReviewService` with `asyncio.TaskGroup` and internal per-call retry, validate merged output before return, and simplify the handler to a single `review_adr` invocation with exception → `_fail_review`. Extend API/frontend types in parallel. Reframe F-01 tests around static synthesis + rating schema rather than LLM missing-section recall.

## Phase 1: Domain & Wire Schema

### Overview

Introduce `SectionRating`, extend `ReviewResult`, add static annotation synthesis, and define per-section / cross-section LLM wire models and prompts.

### Changes Required

#### 1. Domain value objects

**File**: `backend/domain/adr/value_objects.py`

**Intent**: Add `SectionRating` and optional `section_ratings` on `ReviewResult` so every review records a score and feedback per required section.

**Contract**: `SectionRating` fields: `section: str` (SectionName value), `score: int` (0–5, validated), `feedback: str` (non-empty when score ≥ 1). `ReviewResult.section_ratings: tuple[SectionRating, ...] = ()`. Score 0 only from static phase.

#### 2. Static gap synthesis

**File**: `backend/domain/adr/static_review.py` (new)

**Intent**: Centralize Phase 0 logic: given markdown, return static `missing_section` annotations and score-0 `SectionRating` entries for gap sections.

**Contract**: Pure function(s) using `find_missing_or_empty_sections` and `SectionName`; templated `message`, `location` (`## {Section}`), and `suggestion` per gap. Emit exactly one annotation per gap section.

#### 3. LLM wire schemas

**File**: `backend/domain/adr/review_llm_schema.py`

**Intent**: Add structured payloads for per-section rating calls and cross-section inconsistency calls; add merge helper from parallel payloads to domain `ReviewResult`.

**Contract**: `SectionReviewPayload` — `section`, `score` (1–5), `feedback`, optional `annotations` (no `missing_section` kind). `CrossSectionReviewPayload` — `annotations` only (`inconsistency`, optionally `conciseness`). `merge_review_results(static_annotations, static_ratings, section_payloads, cross_payload, markdown, reviewed_at) -> ReviewResult` producing all five `section_ratings` entries.

#### 4. Section-scoped prompts

**File**: `backend/domain/adr/review_instructions.py`

**Intent**: Replace monolithic missing-section instructions with per-section system prompts embedding the rubric from research (universal anchors + section-specific criteria for scores 1–5). Add cross-section inconsistency prompt. Fold conciseness into Context section prompt (full-doc length hint in user message).

**Contract**: `build_section_system_prompt(section: SectionName) -> str` forbids `missing_section`. `build_cross_section_system_prompt() -> str` covers Decision↔Status inconsistency only. `build_section_user_message(section, body, *, doc_markdown for Context conciseness) -> str`. Remove duplicate `_PLACEHOLDER_TOKENS` — import from `required_sections` or shared constant.

#### 5. Domain exports

**File**: `backend/domain/adr/__init__.py`

**Intent**: Export `SectionRating`, `ParsedAdrSections`, and static helpers needed by application layer.

**Contract**: Public re-exports consistent with existing `find_missing_or_empty_sections` pattern.

### Success Criteria

#### Automated Verification

- Domain unit tests for `SectionRating` validation (score bounds, required feedback)
- Static synthesis tests: complete ADR → no static annotations; incomplete fixtures → correct gaps and score-0 ratings
- Prompt builder tests: section prompts exclude `missing_section`; cross-section prompt present
- `cd backend && uv run ruff check . && uv run ty check`
- `cd backend && uv run pytest tests/domain/adr/ -q`

#### Manual Verification

- Spot-check generated prompts include rubric anchors for each section

**Implementation Note**: Pause for manual confirmation before Phase 2.

---

## Phase 2: Parallel Review Service

### Overview

Reshape `AdrReviewService` to run static Phase 0, parallel LLM Phase 1 via `asyncio.TaskGroup` with per-call retries, merge, and post-merge validation before returning.

### Changes Required

#### 1. Configuration

**File**: `backend/infrastructure/config.py`, `.env.example`

**Intent**: Add configurable per-call retry count for parallel LLM invocations.

**Contract**: `review_llm_attempts_per_call: int = Field(default=2, validation_alias="REVIEW_LLM_ATTEMPTS_PER_CALL")` with minimum 1. Wire through `bootstrap.py` into `AdrReviewService`.

#### 2. Review orchestration

**File**: `backend/application/services/adr_review_service.py`

**Intent**: Replace single LLM call with static phase + `asyncio.TaskGroup` over present sections and cross-section task; retry each failing call up to `review_llm_attempts_per_call`; skip LLM for statically gapped sections.

**Contract**: `review_adr(markdown, *, validation_feedback=())` — `validation_feedback` may be deprecated or ignored for MVP (no handler retry); document in code comment. Use `asyncio.TaskGroup` (not `asyncio.gather`) so sibling tasks cancel on first failure and partial parallel failure surfaces as `ExceptionGroup` → map to `AdrReviewFailedError` with section identifier. On any section/cross-section failure after retries, raise that exception. After merge, call updated `validate_review_result`; on failure raise same exception type. Return complete `ReviewResult` with five `section_ratings`.

#### 3. Fake LLM port

**File**: `backend/infrastructure/llm/fake_completion.py`

**Intent**: Return per-section rating payloads when system prompt identifies section scope; return inconsistency payload for cross-section prompt. Remove inline `find_missing_or_empty_sections` — static phase owns gaps.

**Contract**: Heuristic scores from body length/content (deterministic for tests). No `missing_section` from fake LLM.

#### 4. Service factory

**File**: `backend/infrastructure/bootstrap.py` (or `build_adr_review_service` helper)

**Intent**: Pass `review_llm_attempts_per_call` into `AdrReviewService`.

**Contract**: Constructor accepts attempts setting; tests can override.

### Success Criteria

#### Automated Verification

- Service tests: static gaps produce score-0 ratings without LLM calls for gap sections
- Service tests: present sections invoke parallel calls (assert call count via recording port)
- Service tests: per-call retry — failing port succeeds on second attempt
- Service tests: TaskGroup cancels siblings on failure — one section failure after retries raises `AdrReviewFailedError` (not partial merge)
- Service tests: exhausted per-call retries raise `AdrReviewFailedError`
- Service tests: merged result passes validation on complete fixture
- Fake LLM tests updated for section-scoped responses
- `cd backend && uv run pytest tests/application/services/test_adr_review_service.py tests/infrastructure/llm/test_fake_completion.py -q`

#### Manual Verification

- Local `just dev-backend` with `LLM_PROVIDER=fake` completes review for complete and incomplete ADRs

**Implementation Note**: Pause for manual confirmation before Phase 3.

---

## Phase 3: Validation & Handler

### Overview

Simplify `validate_review_result` for the new model; make `RunAiReviewHandler` strict — one service call, any exception or validation failure → `_fail_review`.

### Changes Required

#### 1. Review quality validator

**File**: `backend/application/review_quality.py`

**Intent**: Remove LLM-vs-parser missing-section cross-check (static-only gaps). Add rating schema validation: all five sections present in `section_ratings`, scores 0–5, non-empty `feedback` for scores ≥ 1, no duplicate sections. Retain actionability checks on LLM annotations.

**Contract**: `validate_review_result` returns failures for actionability + rating schema only. `extract_flagged_sections` may remain for harness compatibility or move to static-only helpers.

#### 2. Handler strict failure

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Remove handler `_MAX_ATTEMPTS` retry loop and S-07 "complete with invalid output after exhausted retries" path. Single `review_adr` call; success → `_complete_review`; `AdrReviewFailedError` or other exceptions → `_fail_review`.

**Contract**: Log `handler.run_ai_review.failed` with failure reason. Remove `validation_feedback` threading unless kept for future slice. `_fail_review` code remains `validation_failed` or introduce `review_failed` if clearer — pick one and use consistently in tests.

#### 3. Handler tests

**File**: `backend/tests/application/handlers/test_run_ai_review.py`

**Intent**: Rewrite tests for strict failure semantics and new `ReviewResult` shape (static annotations + ratings).

**Contract**: Remove tests asserting completion after validation failure. Add test: service raises → `AIReviewFailed` persisted. Update `_valid_result` helper to include `section_ratings`.

### Success Criteria

#### Automated Verification

- `test_review_quality.py` updated — no missing-section cross-check tests; rating validation tests added
- Handler tests pass with strict failure behavior
- `cd backend && uv run pytest tests/application/ -q`

#### Manual Verification

- Submit incomplete ADR: static gaps visible only after successful review (not stuck in `in_review` on LLM partial failure)
- Submit ADR that triggers fake LLM failure after retries: user sees `review_error` in panel

**Implementation Note**: Pause for manual confirmation before Phase 4.

---

## Phase 4: API & Frontend

### Overview

Expose `section_ratings` on the ADR API and show a minimal ratings list in the review panel below annotations.

### Changes Required

#### 1. API response schema

**File**: `backend/infrastructure/api/schemas/adr.py`

**Intent**: Add `SectionRatingResponse` and optional `section_ratings` on `AdrResponse`.

**Contract**: Fields mirror domain: `section`, `score`, `feedback`. Nullable/empty when no review yet.

#### 2. API mapper

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Map `ReviewResult.section_ratings` in `_to_adr_response`. Optionally extend `annotation_counts_from_result` or add `section_rating_summary` on `ReviewStatusResponse` — only if needed for polling; otherwise defer.

**Contract**: `GET /adrs/{id}` includes `section_ratings` when `after_review`.

#### 3. Frontend types

**File**: `frontend/composables/useApi.ts`, `frontend/app/stores/adr.ts`

**Intent**: Add `SectionRating` type and map snake_case `section_ratings` on `AdrResponse`.

**Contract**: `Adr` store field `sectionRatings: SectionRating[] | null`.

#### 4. Review panel UI

**File**: `frontend/app/components/adr/AdrReviewAnnotations.vue`

**Intent**: Below existing annotation groups, render a simple "Section ratings" list: section name, score (0–5), feedback text.

**Contract**: Update `showEmptyState` — `after_review` with zero annotations but non-empty ratings is not empty. Pass `sectionRatings` prop from `[id].vue`.

#### 5. Frontend tests

**Files**: `frontend/tests/adr-review-annotations.test.ts`, `frontend/tests/adr-editor-page.test.ts`

**Intent**: Cover ratings display and revised empty-state logic.

**Contract**: Ratings render below annotations; empty state requires both annotations and ratings absent.

### Success Criteria

#### Automated Verification

- API integration test asserts `section_ratings` in `GET /adrs/{id}` response after review
- `cd frontend && pnpm run typecheck && pnpm run lint`
- `cd frontend && pnpm run test -- adr-review-annotations adr-editor-page`

#### Manual Verification

- Complete ADR review in browser: section ratings visible below annotation groups
- Incomplete ADR: score-0 static ratings and missing-section annotations visible together

**Implementation Note**: Pause for manual confirmation before Phase 5.

---

## Phase 5: Tests, Docs & S-07 Close-Out

### Overview

Reframe F-01 harness, update PRD and roadmap, mark S-07 superseded.

### Changes Required

#### 1. F-01 harness rework

**Files**: `backend/tests/review_quality/test_runtime_validation.py`, `grader.py`, `test_grader.py`, `test_harness_metrics.py`, `cases.py`

**Intent**: Demote LLM missing-section precision/recall grader. Add tests for static synthesis regression and rating schema on merged fixtures. Retain actionability grader.

**Contract**: Remove or rewrite `test_runtime_validation` fake-LLM 80% recall assertion. `grade_review_output` focuses on actionability + static gap presence in merged results.

#### 2. PRD update

**File**: `context/foundation/prd.md`

**Intent**: Reshape AI review output requirements to describe static gap detection + per-section 0–5 ratings + existing annotation kinds. Remove "80% section gap detection accuracy" NFR. Update Business Logic input/output section. Note FR-008 still "one review per submit" — internal parallel calls are implementation detail.

**Contract**: FR-010 references static missing sections + per-section quality ratings. FR-011/FR-012 unchanged in user outcome. Actionability NFR retained.

#### 3. Roadmap update

**File**: `context/foundation/roadmap.md`

**Intent**: Close S-07 as superseded by `adr-validation-re-shape`. Add or elevate this change as current post-core focus. Update S-09 prerequisite note (S-07 → this slice or remove S-07 dep).

**Contract**: S-07 status `superseded`; link to `adr-validation-re-shape`. Stream B narrative updated.

#### 4. Change records

**Files**: `context/changes/review-validation-logs-only/change.md`, `context/changes/adr-validation-re-shape/change.md`

**Intent**: Mark S-07 change `superseded` with pointer to this slice. Set `adr-validation-re-shape` status `planned` → `implementing` when work starts.

**Contract**: `review-validation-logs-only` notes why superseded (strict validation reshape replaces logs-only gate).

### Success Criteria

#### Automated Verification

- `cd backend && uv run pytest tests/review_quality/ -q`
- `cd backend && uv run pytest` (full backend suite)
- `pre-commit run --all-files` passes on touched files

#### Manual Verification

- PRD Business Logic section accurately describes static + ratings + annotations flow
- Roadmap shows S-07 superseded and S-09 prerequisite updated

---

## Testing Strategy

### Unit Tests

- Static synthesis for all seven F-01 fixtures
- `SectionRating` and merge validation edge cases (duplicate section, score 6, empty feedback)
- Per-section prompt content (no `missing_section` instruction)
- Per-call retry exhaustion and success-on-retry
- Handler strict fail vs complete paths

### Integration Tests

- End-to-end submit → review → `GET /adrs/{id}` with `section_ratings` and static annotations
- Review failure path: ADR stays `in_review` with `review_error` when parallel call fails

### Manual Testing Steps

1. Submit complete ADR — all five ratings 1–5, annotations if inconsistency/conciseness triggered
2. Submit ADR missing Context — score 0 for Context, LLM calls only for present sections
3. Set `REVIEW_LLM_ATTEMPTS_PER_CALL=1` with flaky provider — verify `_fail_review`
4. Verify polling still transitions to `after_review` on success; shows error on failure

## Performance Considerations

Six parallel LLM calls per review (five sections + cross-section) replace one monolithic call. Acceptable for MVP — event-driven review with frontend polling. No semaphore or rate limiting in this slice. Cost monitoring deferred.

## Migration Notes

No database migration. Existing `review_annotations` JSONB rows deserialize with `section_ratings=()`. Old reviews display annotations only until re-reviewed.

## References

- Research: `context/changes/adr-validation-re-shape/research.md`
- Static parser: `backend/domain/adr/required_sections.py`
- Superseded S-07: `context/changes/review-validation-logs-only/plan.md`
- Per-section rubric: research.md § Per-section rating rubric (0–5)

## Progress

### Phase 1: Domain & Wire Schema

#### Automated

- [x] 1.1 Domain unit tests for SectionRating validation and static synthesis — dfdb01a
- [x] 1.2 Prompt builder tests for section and cross-section prompts — dfdb01a
- [x] 1.3 `cd backend && uv run ruff check . && uv run ty check` — dfdb01a
- [x] 1.4 `cd backend && uv run pytest tests/domain/adr/ -q` — dfdb01a

#### Manual

- [x] 1.5 Spot-check generated prompts include rubric anchors per section — dfdb01a

### Phase 2: Parallel Review Service

#### Automated

- [x] 2.1 Service tests for static phase, parallel calls, per-call retry, and failure raising — 394de65
- [x] 2.2 Fake LLM tests updated for section-scoped responses — 394de65
- [x] 2.3 `cd backend && uv run pytest tests/application/services/test_adr_review_service.py tests/infrastructure/llm/test_fake_completion.py -q` — 394de65

#### Manual

- [ ] 2.4 Local fake-provider review completes for complete and incomplete ADRs

### Phase 3: Validation & Handler

#### Automated

- [x] 3.1 `test_review_quality.py` updated for rating schema validation
- [x] 3.2 Handler tests pass with strict failure behavior
- [x] 3.3 `cd backend && uv run pytest tests/application/ -q`

#### Manual

- [ ] 3.4 Incomplete ADR review succeeds with static gaps; partial LLM failure shows review_error

### Phase 4: API & Frontend

#### Automated

- [ ] 4.1 API integration test asserts section_ratings in GET response
- [ ] 4.2 `cd frontend && pnpm run typecheck && pnpm run lint`
- [ ] 4.3 `cd frontend && pnpm run test -- adr-review-annotations adr-editor-page`

#### Manual

- [ ] 4.4 Browser: ratings visible below annotations; score-0 gaps display correctly

### Phase 5: Tests, Docs & S-07 Close-Out

#### Automated

- [ ] 5.1 `cd backend && uv run pytest tests/review_quality/ -q`
- [ ] 5.2 `cd backend && uv run pytest`
- [ ] 5.3 `pre-commit run --all-files` on touched files

#### Manual

- [ ] 5.4 PRD and roadmap accurately reflect superseded S-07 and new validation model
