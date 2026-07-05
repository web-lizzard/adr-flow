---
date: 2026-06-19T00:00:00+00:00
researcher: Composer
git_commit: b7419b893f5125c856f666f1a8186fc4d0629bea
branch: main
repository: adr-flow
topic: "S-07 review-validation-logs-only — always deliver LLM review to after_review; log validation failures only"
tags: [research, codebase, run-ai-review, review-quality, s-07]
status: complete
last_updated: 2026-06-19
last_updated_by: Composer
---

# Research: S-07 Review Validation Logs Only

**Date**: 2026-06-19
**Researcher**: Composer
**Git Commit**: `b7419b893f5125c856f666f1a8186fc4d0629bea`
**Branch**: main
**Repository**: adr-flow

## Research Question

What must change for S-07 (`review-validation-logs-only`) so users always receive LLM review annotations in `after_review`, with failed quality checks logged for measurement but never blocking the `in_review → after_review` transition?

## Summary

Today, `RunAiReviewHandler` treats `validate_review_result()` as a **hard runtime gate**: invalid LLM output is retried once with `validation_feedback`, then `_fail_review` persists `AIReviewFailed`, sets `review_error`, and leaves the ADR **stuck in `in_review`** with no edit or resubmit path. S-07 reverses only the **validation** branch of this behavior — keep the F-01 harness and `validate_review_result` for measurement, log failures at `handler.run_ai_review.validation_failed`, and always call `_complete_review` with whatever the LLM returned. The primary code change is in `backend/application/handlers/run_ai_review.py`; tests in handler, API integration, and some frontend polling/error paths need updates. Provider/LLM exceptions are a separate open design question (roadmap text targets quality-check failures only).

## Detailed Findings

### Current blocking path (`run_ai_review.py`)

The handler runs up to `_MAX_ATTEMPTS = 2` LLM calls per submit event:

1. Call `adr_review_service.review_adr(markdown, validation_feedback=...)`
2. Run `validate_review_result(markdown, result)` from `application/review_quality.py`
3. **If validation passes** → `_complete_review` → `AIReviewCompleted` → status `after_review`
4. **If validation fails** → log warning, set `validation_feedback`, retry
5. **After exhausted attempts** (validation or LLM exception) → `_fail_review` → `AIReviewFailed` with `code="validation_failed"` → status stays `in_review`

Key code:

```82:128:backend/application/handlers/run_ai_review.py
                validation = validate_review_result(markdown, result)
                if validation.passed:
                    ...
                    await self._complete_review(stored_event, adr_id, result)
                    ...
                    return
                last_error = "; ".join(validation.failures)
                validation_feedback = validation.failures
                self._logger.warning(
                    "handler.run_ai_review.validation_failed",
                    ...
                )
            ...
        await self._fail_review(
            stored_event,
            adr_id,
            last_error or "Review failed",
        )
```

`_fail_review` always uses `code = "validation_failed"` even when the terminal error was an LLM provider exception.

### What `validate_review_result` checks

`backend/application/review_quality.py` enforces two rule sets from F-01:

| Check | Rule | Failure examples |
|-------|------|------------------|
| Missing-section coverage | Compare `find_missing_or_empty_sections(markdown)` vs `missing_section` annotations | `false negative: missing annotation for Decision`; `false positive: unexpected missing_section annotation for Context` |
| Actionability | Per-kind required fields via `required_fields_for_kind` | `annotation 0 (inconsistency): non-empty location required` |

The harness and unit tests (`tests/application/test_review_quality.py`, `tests/review_quality/`) remain valuable under S-07 — only the **gating** in the handler changes.

### Aggregate and projection behavior on failure

- `adr.fail_review()` (`domain/adr/aggregate.py`) requires `in_review`, sets `review_error`, clears `review_result`, **does not change status**
- `adr.complete_review()` transitions `in_review → after_review`, sets annotations, clears `review_error`
- `record_review_failure` projection updates `review_error` only — status stays `in_review`

A validation terminal failure therefore strands the ADR: user cannot edit (`AdrEditWhileInReview`), cannot resubmit (`AdrInvalidSubmitStatus` — only `draft` accepted), and the handler won't reprocess the same submit event (`_skip_reason: duplicate_failure`).

### User-facing stuck state

| Layer | Current behavior on validation failure |
|-------|--------------------------------------|
| API `GET /review-status` | `status: "in_review"`, `review_error.code: "validation_failed"` |
| Frontend polling (`useAdrReviewPolling.ts`) | Stops when `reviewError` appears |
| Editor (`[id].vue`) | Stays disabled in `in_review` |
| Review panel (`AdrReviewAnnotations.vue`) | Shows "Review failed" alert |

### Historical context: F-01 → S-04 → S-07

| Slice | Role | Runtime behavior |
|-------|------|------------------|
| **F-01** (`review-quality-checks`, archived) | Pytest eval harness for section detection + actionability; quality gate **contract** for S-04 | No runtime handler |
| **S-04** (`first-ai-review-annotations`, archived) | Wired harness into `review_quality.py` + `run_ai_review.py` | **Blocking** — failed validation keeps ADR in `in_review` |
| **S-07** (this change) | Relax runtime gate; keep harness for measurement | **Logs only** — always transition to `after_review` |

Roadmap positions S-07 as highest-leverage post-core fix and prerequisite for S-09 (conditional re-review).

### PRD alignment

PRD defines **what** good output looks like and **when** users see annotations (`after_review`), but does **not** specify whether quality-check failures may block the transition:

- **FR-008**: one AI review per ADR on "Publish for review"
- **FR-010–012**: missing-section, inconsistency, conciseness annotations visible at `after_review`
- **NFRs**: ≥80% section gap accuracy; actionability of each annotation

S-07 treats NFRs as **measurement targets** (logs) rather than **enforcement gates** — a deliberate product relaxation not spelled out in the PRD.

### Tests requiring updates for S-07

**Handler** (`backend/tests/application/handlers/test_run_ai_review.py`):

| Test | Current expectation | S-07 change |
|------|---------------------|-------------|
| `test_run_ai_review_records_terminal_failure_after_retry_exhausted` | `AIReviewFailed`, `validation_failed` | Rewrite: expect `AIReviewCompleted` even with invalid output |
| `test_run_ai_review_retries_once_on_invalid_output_then_succeeds` | 2 LLM calls with feedback | Optional: keep retry as optimization or remove if completing on first invalid result |
| Others (idempotency, skip, happy path) | — | Likely unchanged |

**API integration** (`backend/tests/infrastructure/api/test_adr_api.py`):

- `test_review_status_exposes_failure_metadata_after_invalid_review` — expect `after_review`, no `review_error`
- `test_replay_processes_unprocessed_submit_event` — same flip

**Frontend** (only if validation failures stop emitting `review_error`):

- `frontend/tests/adr-review-polling.test.ts` — tests for polling stop on `review_error` become validation-irrelevant
- `frontend/tests/adr-editor-page.test.ts` — `shows review error metadata in the annotation panel` narrows to provider-failure only

**Unchanged**: `validate_review_result` unit tests, domain aggregate `fail_review` tests (still needed for LLM errors), projection `record_review_failure` contract, fakes `stream_with_review_failure` (historical idempotency).

### Fakes and fixtures

- `after_review_stream` (`fakes.py:214–243`) — becomes expected end state for previously-blocking invalid results
- `stream_with_review_failure` — keep for idempotency tests on historical `AIReviewFailed` events

## Code References

- `backend/application/handlers/run_ai_review.py:15` — `_MAX_ATTEMPTS = 2`
- `backend/application/handlers/run_ai_review.py:82-99` — validation gate and retry feedback
- `backend/application/handlers/run_ai_review.py:124-128` — terminal `_fail_review` call
- `backend/application/handlers/run_ai_review.py:206-265` — `_fail_review` persistence path
- `backend/application/review_quality.py:24-32` — `validate_review_result` entry point
- `backend/domain/adr/aggregate.py` — `complete_review` vs `fail_review` status rules
- `backend/tests/application/handlers/test_run_ai_review.py:177-215` — primary blocking test to rewrite
- `frontend/app/composables/useAdrReviewPolling.ts` — polling stops on `reviewError`
- `context/foundation/roadmap.md:171-181` — S-07 outcome and risk statement

## Architecture Insights

1. **Separation of concerns is already clean**: F-01 rules live in `review_quality.py`; handler owns gating. S-07 is a small handler change plus test updates — no domain model changes required if validation failures always complete.
2. **`fail_review` / `AIReviewFailed` may still be needed** for true LLM/provider failures unless S-07 scope expands to "never block on anything."
3. **Retry loop decouples naturally**: validation feedback retry is an optimization when gating is removed; planner should decide whether to keep one retry for quality improvement or simplify to single-call complete.
4. **Idempotency is event-stream based**: `_skip_reason` checks `after_review` and duplicate `AIReviewFailed` per `source_event_id` — completing on invalid output means fewer `AIReviewFailed` events going forward.
5. **Lessons apply**: if new domain invariants are added, use typed `DomainError` subclasses (`context/foundation/lessons.md`).

## Historical Context (from prior changes)

- `context/archive/2026-06-16-review-quality-checks/plan.md` — F-01 eval harness; S-04 imports graders for runtime validation
- `context/archive/2026-06-16-review-quality-checks/research.md` — harness-only scope; hard threshold deferred to S-04
- `context/archive/2026-06-17-first-ai-review-annotations/plan.md` — wired blocking validation; failure keeps ADR in `in_review` with `review_error`
- `context/archive/2026-06-18-llm-refactor/plan.md` — prompt/validation parity; explicitly kept `validate_review_result` gate semantics unchanged
- `context/foundation/roadmap.md:92,132` — documents blocking validation as delivered risk S-07 fixes

## Related Research

- `context/changes/valid-adr-example/research.md` — two-level validation (markdown parser vs `validate_review_result`)
- `context/archive/2026-06-18-llm-refactor/research.md` — handler retry and validation gate analysis

## Open Questions

1. **Scope of "never block"**: validation failures only, or also LLM provider/parse exceptions? Today both converge on `_fail_review` with `code="validation_failed"`.
2. **Retry behavior**: keep one validation-feedback retry as quality optimization, or complete on first LLM response regardless?
3. **Logging contract**: enrich `handler.run_ai_review.validation_failed` with structured fields for F-01 metric correlation? Any separate counter/dashboard?
4. **User-visible quality signal**: show raw LLM output silently when checks fail, or surface a non-blocking warning in UI?
5. **Re-enable gating criteria**: roadmap mentions "until review quality is stable enough" — no threshold defined.
6. **PRD note**: worth documenting that NFRs are measurement targets in MVP, not blocking gates?
7. **S-09 dependency**: S-07 must ship first so users always see first-review output before optional conditional re-review.
