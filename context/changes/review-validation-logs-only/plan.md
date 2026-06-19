# S-07 Review Validation Logs Only — Implementation Plan

## Overview

Relax the runtime validation gate in `RunAiReviewHandler` so F-01 quality checks (`validate_review_result`) continue to run and log failures for measurement, but never block the `in_review → after_review` transition. Users always receive whatever the LLM returned. Provider/LLM exceptions after retry exhaustion still call `_fail_review` and leave the ADR stuck in `in_review` with `review_error`.

## Current State Analysis

Today `RunAiReviewHandler` runs up to two LLM attempts per submit event. When `validate_review_result` fails on both attempts, the handler calls `_fail_review`, emits `AIReviewFailed` with `code="validation_failed"`, and leaves the ADR in `in_review`. The user cannot edit (`AdrEditWhileInReview`), cannot resubmit (`AdrInvalidSubmitStatus`), and the handler skips reprocessing (`duplicate_failure`).

F-01 rules live in `application/review_quality.py` and remain unchanged. The gating decision is entirely in `application/handlers/run_ai_review.py`.

### Key Discoveries:

- `backend/application/handlers/run_ai_review.py:82-128` — validation gate, retry feedback, terminal `_fail_review`
- `backend/application/review_quality.py:24-32` — harness entry point; no changes needed
- `backend/domain/adr/aggregate.py` — `complete_review` transitions to `after_review`; `fail_review` does not change status
- `backend/tests/application/handlers/test_run_ai_review.py:177-215` — primary test asserting blocking behavior
- `backend/tests/infrastructure/api/test_adr_api.py:447-507, 590-593` — API tests expecting `in_review` + `review_error` on invalid output
- Frontend `review_error` UI is generic; no production code changes needed when validation stops emitting errors (research confirmed)

## Desired End State

After implementation:

1. Submitting an ADR for review always ends in `after_review` when the LLM returns a parseable `ReviewResult`, even if F-01 validation fails on every attempt.
2. `handler.run_ai_review.validation_failed` warning logs still fire per failed attempt with `failures` tuple.
3. When the final attempt throws an LLM/provider exception, `_fail_review` still runs — ADR stays `in_review` with `review_error`.
4. PRD documents that section-gap and actionability NFRs are MVP measurement targets, not runtime enforcement gates.
5. No user-visible quality warning when validation fails but output is delivered (silent raw annotations).

### Verification

- Handler unit tests: invalid output after retry exhaustion → `AIReviewCompleted`, not `AIReviewFailed`
- API integration: `GET /review-status` and `GET /adrs/{id}` return `after_review` with `review_error: null` after invalid LLM output
- Provider failure path: existing `_fail_review` behavior preserved (no new tests required unless regressions appear)
- `cd backend && uv run pytest` and `uv run ruff check .` pass

## What We're NOT Doing

- Changing `validate_review_result` rules or F-01 eval harness
- Domain model changes (`complete_review`, `fail_review`, events)
- Frontend production code or frontend test updates
- Fixing `_fail_review` always using `code="validation_failed"` for provider errors (pre-existing; out of scope)
- User-visible quality warnings when validation fails
- Enriched structured logging beyond current `handler.run_ai_review.validation_failed` fields
- Conditional re-review (S-09) — separate slice, depends on S-07 shipping first

## Implementation Approach

Track `last_result: ReviewResult | None` across the retry loop. On each successful `review_adr` call, store the result before validation. Keep the existing pass → `_complete_review` early return. Keep validation-failure logging and `validation_feedback` for the retry optimization.

After the loop exits without an early return:

- If the **final attempt** ended with a caught exception → `_fail_review` (provider failure path, unchanged)
- Else if `last_result is not None` → `_complete_review(last_result)` (validation exhausted but LLM output exists)
- Else → `_fail_review` (defensive; should not occur in normal operation)

Mixed outcomes follow naturally: validation fail on attempt 1 + provider exception on attempt 2 → `_fail_review`; provider exception on attempt 1 + validation fail on attempt 2 → `_complete_review` with attempt 2 output.

## Critical Implementation Details

**Terminal-state discrimination** — The implementer must distinguish "exhausted validation retries with a result" from "exhausted provider retries" using whether the final loop iteration caught an exception, not merely whether `last_result` is set. A validation failure on attempt 1 followed by a provider exception on attempt 2 must still `_fail_review` even though `last_result` holds attempt 1's output.

## Phase 1: Handler Behavior

### Overview

Change `RunAiReviewHandler.handle` so validation failures no longer converge on `_fail_review`. Provider exception handling and `_MAX_ATTEMPTS = 2` retry loop stay intact.

### Changes Required:

#### 1. RunAiReviewHandler retry loop

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: After validation retries are exhausted, deliver the last LLM result to the user instead of failing the review. Preserve `_fail_review` only when the final attempt raises an exception.

**Contract**: Introduce `last_result: ReviewResult | None` and `final_attempt_exception: bool` (or equivalent) in `handle`. After the `for attempt` loop, branch: `_fail_review` when `final_attempt_exception` is true; `_complete_review(last_result)` when `last_result` is not None; otherwise `_fail_review`. Remove or repurpose the terminal `handler.run_ai_review.failed` error log for validation-only exhaustion — validation exhaustion should log at warning level (existing `validation_failed` per attempt) then complete at info level via existing `handler.run_ai_review.completed`.

#### 2. _fail_review scope

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: `_fail_review` remains the terminal path for provider/LLM exceptions only under S-07. No signature changes.

**Contract**: `_fail_review` is called only from the post-loop branch when the final attempt caught an exception (or defensive no-result fallback). Validation-only exhaustion must not reach `_fail_review`.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run ruff check .` passes
- `cd backend && uv run ty check` passes

#### Manual Verification:

- Trace handler logic for four scenarios: (1) valid on first attempt, (2) invalid then valid on retry, (3) invalid both attempts, (4) exception on final attempt — confirm correct terminal branch
- Confirm `validate_review_result` and `review_quality.py` are untouched

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Backend Tests

### Overview

Update handler and API integration tests to assert the new terminal state for validation failures. Keep idempotency and provider-failure tests intact.

### Changes Required:

#### 1. Handler unit tests

**File**: `backend/tests/application/handlers/test_run_ai_review.py`

**Intent**: Replace blocking expectations with completion expectations for validation exhaustion.

**Contract**:

- `test_run_ai_review_records_terminal_failure_after_retry_exhausted` — rename to reflect completion; assert `AIReviewCompleted` (not `AIReviewFailed`), no `recorded_failures`, `applied_results` contains the invalid `ReviewResult`, both attempts called with feedback on second call
- `test_run_ai_review_retries_once_on_invalid_output_then_succeeds` — unchanged behavior (still expects 2 LLM calls)
- `test_run_ai_review_skips_when_failure_already_recorded_for_event` — unchanged (historical `AIReviewFailed` idempotency via `stream_with_review_failure`)
- Consider adding `test_run_ai_review_fails_when_final_attempt_raises` if no existing test covers provider exception terminal path

#### 2. API integration tests

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: Flip invalid-review API expectations from stuck `in_review` to completed `after_review`.

**Contract**:

- `test_review_status_exposes_failure_metadata_after_invalid_review` — rename (e.g. `test_invalid_review_still_completes_to_after_review`); assert `status == "after_review"`, `review_error is None`, `reviewed_at is not None` on both review-status and full ADR GET
- `test_replay_processes_unprocessed_submit_event` — post-drain assertions: `status == "after_review"`, `review_error is None`, `review_service.calls == 2` (retry kept)

#### 3. Fakes (no code changes expected)

**File**: `backend/tests/application/commands/fakes.py`

**Intent**: Document expected usage; fakes remain as-is.

**Contract**: `after_review_stream` models new terminal state for invalid results; `stream_with_review_failure` remains for historical idempotency tests.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py` passes
- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "invalid_review or replay_processes"` passes
- `cd backend && uv run pytest tests/application/test_review_quality.py` passes (unchanged harness)
- `cd backend && uv run pytest` passes (full backend suite)

#### Manual Verification:

- No frontend test files modified (per scope decision)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: PRD Amendment

### Overview

Document that section-gap and actionability NFRs are measurement targets evaluated via logs and the F-01 harness, not runtime gates that block review delivery.

### Changes Required:

#### 1. Non-Functional Requirements section

**File**: `context/foundation/prd.md`

**Intent**: Clarify MVP enforcement policy for the two review-quality NFRs without changing their target values.

**Contract**: Under `## Non-Functional Requirements`, add a short note after the section-gap and actionability bullets (or a single parenthetical block covering both) stating that in MVP these thresholds are **measurement targets** logged by `handler.run_ai_review.validation_failed`, not runtime gates — users always receive LLM annotations in `after_review` regardless of check outcome. Reference S-07 / `review-validation-logs-only` change ID.

### Success Criteria:

#### Automated Verification:

- Markdown renders correctly (no broken structure in `prd.md`)

#### Manual Verification:

- Wording is consistent with roadmap S-07 outcome and does not contradict FR-010–012 ("user sees annotations at `after_review`")

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Handler: validation exhaustion → `AIReviewCompleted` with invalid `ReviewResult` persisted
- Handler: retry passes validation feedback on second call
- Handler: historical `AIReviewFailed` idempotency skip unchanged
- `validate_review_result` unit tests unchanged

### Integration Tests:

- API: invalid `ReviewResult` from fake LLM → `after_review`, no `review_error`
- API: replay with counting invalid service → 2 LLM calls, `after_review` terminal state
- API: happy-path submit → `after_review` (regression guard)

### Manual Testing Steps:

1. Start dev stack (`just dev`), submit an ADR, confirm transition to `after_review` with annotations visible
2. If possible with fake/invalid LLM config, confirm validation failure logs appear in backend output without `review_error` in API response
3. Confirm editor unlocks after review completes (no stuck `in_review`)

## Performance Considerations

No meaningful change — same two-attempt retry loop, same LLM call count. Slightly fewer `AIReviewFailed` events and projection writes on validation exhaustion.

## Migration Notes

No data migration. Historical ADRs stuck in `in_review` with `validation_failed` from pre-S-07 runs are not auto-healed — out of scope. New submits after deploy follow the relaxed path.

## References

- Research: `context/changes/review-validation-logs-only/research.md`
- Roadmap S-07: `context/foundation/roadmap.md:171-181`
- Prior blocking implementation: `context/archive/2026-06-17-first-ai-review-annotations/plan.md`
- Handler: `backend/application/handlers/run_ai_review.py`
- Validation harness: `backend/application/review_quality.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Handler Behavior

#### Automated

- [x] 1.1 `cd backend && uv run ruff check .` passes
- [x] 1.2 `cd backend && uv run ty check` passes

#### Manual

- [x] 1.3 Trace handler logic for four terminal scenarios (valid first, invalid→valid retry, invalid both, exception final)

### Phase 2: Backend Tests

#### Automated

- [ ] 2.1 `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py` passes
- [ ] 2.2 `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "invalid_review or replay_processes"` passes
- [ ] 2.3 `cd backend && uv run pytest tests/application/test_review_quality.py` passes
- [ ] 2.4 `cd backend && uv run pytest` passes (full backend suite)

#### Manual

- [ ] 2.5 Confirm no frontend test files were modified

### Phase 3: PRD Amendment

#### Automated

- [ ] 3.1 `prd.md` markdown structure intact

#### Manual

- [ ] 3.2 NFR wording consistent with FR-010–012 and roadmap S-07
