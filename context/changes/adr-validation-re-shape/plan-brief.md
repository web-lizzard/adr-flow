# ADR Validation Reshape — Plan Brief

> Full plan: `context/changes/adr-validation-re-shape/plan.md`
> Research: `context/changes/adr-validation-re-shape/research.md`

## What & Why

Replace the single monolithic LLM review with deterministic static gap detection plus parallel per-section quality scoring (0–5), so missing sections are always caught pre-LLM and each present section gets an independent compliance rating with actionable feedback.

## Starting Point

`AdrReviewService` makes one LLM call for the full document; `validate_review_result` cross-checks LLM missing-section output against a parser that already exists but runs only post-LLM. S-07 partially landed (complete with invalid output after retries) but is superseded by this reshape.

## Desired End State

Reviews run static analysis first (score 0 + `missing_section` for gaps), then up to six parallel LLM calls (five sections + cross-section inconsistency). All five sections appear in `section_ratings`. Partial LLM failure fails the review. Users see ratings below annotations in the review panel. PRD and roadmap reflect the new model; S-07 closed as superseded.

## Key Decisions Made

| Decision | Choice | Why | Source |
| -------- | ------ | --- | ------ |
| Re-review eligibility | Out of scope (S-09) | Separate slice | Plan |
| `missing_section` source | Static-only | Eliminates LLM false neg/pos; score 0 is deterministic | Research / Plan |
| Partial parallel failure | Fail pipeline (`_fail_review`) | Whole review must validate | Plan |
| Retry policy | Per-call only, default 2 (`REVIEW_LLM_ATTEMPTS_PER_CALL`) | User-configurable; handler retry deferred | Plan |
| Post-merge validation failure | Fail review | Consistent with strict model; recovery UX later | Plan |
| Cross-section inconsistency | Separate parallel call | Clean isolation of Decision↔Status rules | Research / Plan |
| Conciseness | Folded into Context section call | Fewer calls than separate doc-level task | Research / Plan |
| Ratings UI | Simple list below annotations | Visible now; re-style deferred | Plan |
| Gap detection NFR | Drop for MVP | Gaps are deterministic via parser | Plan |
| Latency / cost | Parallel OK; not prioritized | Event-driven review with polling | Plan |
| S-07 | Close as superseded | Strict reshape replaces logs-only gate | Plan |

## Scope

**In scope:** Domain schema (`SectionRating`), static Phase 0, parallel LLM orchestration, per-call retries setting, strict handler failure, API `section_ratings`, minimal frontend display, F-01 harness rework, PRD + roadmap update, S-07 supersession.

**Out of scope:** S-09 re-review eligibility, handler-level retry, post-failure resubmit UX, polished ratings UI, cost/rate limits, rubric golden-score calibration, finishing S-07 logs-only tests.

## Architecture / Approach

```
ADRSubmittedForReview
  → RunAiReviewHandler (single attempt, strict)
      → AdrReviewService.review_adr
          Phase 0: find_missing_or_empty_sections → static annotations + score-0 ratings
          Phase 1: asyncio.TaskGroup(5 section LLM + 1 cross-section LLM), per-call retries
          Phase 2: merge → validate_review_result (actionability + ratings) → ReviewResult
      → success: AIReviewCompleted | failure: AIReviewFailed
```

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Domain & wire schema | `SectionRating`, static builder, prompts, merge contract | Rubric prompt size / token limits per section |
| 2. Parallel review service | `asyncio.TaskGroup`, per-call retries, fake LLM mirror | Partial failure handling across 6 calls |
| 3. Validation & handler | Strict fail; drop missing-section cross-check | Breaking change vs S-07 partial landing |
| 4. API & frontend | `section_ratings` exposed and displayed minimally | Empty-state logic with ratings-only reviews |
| 5. Tests & docs | F-01 rework, PRD/roadmap, close S-07 | Test churn across harness and handler |

**Prerequisites:** S-04 first AI review shipped; static parser in `required_sections.py`.

**Estimated effort:** ~3–4 implementation sessions across 5 phases.

## Open Risks & Assumptions

- Six parallel calls per review increases LLM cost (accepted; monitoring deferred).
- Strict failure may strand users in `in_review` with `review_error` until resubmit UX ships.
- Existing ADRs in DB lack `section_ratings` until re-reviewed (empty default is OK).
- `validation_feedback` handler retry path removed — merge validation failures have no auto-recovery in this slice.

## Success Criteria (Summary)

- Incomplete ADRs always get deterministic gap annotations and score-0 ratings without LLM calls for missing sections.
- Complete ADRs get five section ratings (1–5) plus any inconsistency/conciseness annotations.
- Any parallel LLM failure after per-call retries fails the review; no partial delivery.
- Users see section ratings in the review panel below annotations.
