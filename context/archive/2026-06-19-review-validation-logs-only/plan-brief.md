# S-07 Review Validation Logs Only — Plan Brief

> Full plan: `context/changes/review-validation-logs-only/plan.md`
> Research: `context/changes/review-validation-logs-only/research.md`

## What & Why

Users always receive LLM review annotations in `after_review`. When F-01 quality checks fail, the failure is logged for measurement but the ADR still transitions out of `in_review` — fixing ADRs stranded with no edit or resubmit path.

## Starting Point

S-04 wired the F-01 eval harness into `validate_review_result` and made it a **hard runtime gate** in `RunAiReviewHandler`. Failed validation after two attempts emits `AIReviewFailed`, sets `review_error`, and leaves the ADR stuck in `in_review`.

## Desired End State

Invalid LLM output still runs through `validate_review_result` and logs `handler.run_ai_review.validation_failed`, but the handler calls `_complete_review` with the last LLM result. Provider exceptions after retry exhaustion still `_fail_review`. PRD documents NFRs as measurement targets. UI shows raw annotations silently — no quality warning.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Never-block scope | Validation failures only | Roadmap S-07 targets quality-check gating, not provider resilience | Research / Plan |
| Retry policy | Keep one validation-feedback retry | Optimization without re-blocking on exhaustion | Plan |
| Provider failures | Keep `_fail_review` | Preserve existing stuck-state behavior for true LLM errors | Plan |
| UI signal | Silent — raw annotations only | Unblocks core loop without new UI work | Plan |
| Logging | Keep current warning log | Sufficient for MVP measurement | Research / Plan |
| Frontend tests | Backend only | Production UI already handles `after_review` path generically | Plan |
| PRD | Amend NFR section | Document non-blocking NFR policy for future readers | Plan |

## Scope

**In scope:**

- Handler terminal-branch change in `run_ai_review.py`
- Handler + API integration test updates
- PRD NFR measurement-target note

**Out of scope:**

- `review_quality.py` rule changes
- Domain model / event schema changes
- Frontend code and frontend tests
- Fixing `validation_failed` code on provider errors
- Auto-healing pre-S-07 stuck ADRs

## Architecture / Approach

Single handler change: track `last_result` and whether the final attempt threw. Validation pass → early `_complete_review`. Loop exit → `_complete_review(last_result)` unless final attempt was an exception → `_fail_review`. F-01 harness unchanged; only gating removed.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Handler behavior | Validation exhaustion completes instead of failing | Terminal-branch logic for mixed validation+exception attempts |
| 2. Backend tests | Handler + API tests match new contract | Test renames may miss `-k` filter coverage |
| 3. PRD amendment | NFR policy documented | Wording must not contradict FR-010–012 |

**Prerequisites:** S-04 (first AI review annotations) — delivered
**Estimated effort:** ~1 session across 3 small phases

## Open Risks & Assumptions

- Historical ADRs stuck in `in_review` with `validation_failed` are not migrated
- `_fail_review` still labels provider errors as `code="validation_failed"` (pre-existing)
- S-09 conditional re-review assumes users can always see first-review output

## Success Criteria (Summary)

- Invalid LLM output → `after_review` with annotations, no `review_error`
- Validation failures still logged at `handler.run_ai_review.validation_failed`
- Provider exceptions after retries still block in `in_review`
- Full backend test suite passes
