---
date: 2026-07-05T03:10:00+02:00
researcher: Cursor Agent
git_commit: 486ff38ce33d32c4d532800ad1d56668c08c9f39
branch: main
repository: adr-flow
topic: "in_review always ends with after_review or review_failed (infrastructure error); user decides post-review actions"
tags: [research, codebase, adr, review-status, after_review, in_review, review_failed, ratings]
status: complete
last_updated: 2026-07-05
last_updated_by: Cursor Agent
---

# Research: in_review always ends with after_review or review_failed

**Date**: 2026-07-05T03:10:00+02:00
**Researcher**: Cursor Agent
**Git Commit**: `486ff38ce33d32c4d532800ad1d56668c08c9f39`
**Branch**: main
**Repository**: adr-flow

## Research Question

After switching to rating, leave decisions about what to do after review to the user. The `in_review` state should always end with `after_review` or `error` when problems are at the infrastructure level (the latter is already implemented).

## Summary

**The core invariant is already shipped** via the archived `error-status` change (2026-07-04). Today:

1. **Content / quality / validation issues** → `after_review` with section ratings (0–5) and annotations. `validate_review_result` logs warnings only and never blocks the transition. The user edits and publishes when ready.
2. **Infrastructure / provider / worker failures** → `review_failed` with structured `review_error` (`kind`, message). Retry is available for `retryable_internal_error`.

The domain aggregate exposes exactly two intentional exits from `in_review`: `complete_review` → `after_review` and `fail_review` → `review_failed`. There is no domain path that keeps an ADR in `in_review` after a review outcome is recorded.

**What remains for this change** is not re-implementing the happy path but **formalizing, hardening, and cleaning up** the invariant:

- Document the terminal-semantics contract in PRD/roadmap alignment and tests.
- Remove or update **legacy frontend paths** that still assume `in_review` + `review_error` (pre-`review_failed` model).
- Address **edge-case gaps** where the handler can skip without emitting an outcome event (`adr_not_found`, crash before persist).
- Clarify naming: product "error" maps to status `review_failed`, not a stuck `in_review`.

## Detailed Findings

### Domain layer — two terminal exits from `in_review`

`AdrStatus` defines five lifecycle values including `in_review`, `after_review`, and `review_failed`:

```10:15:backend/domain/adr/value_objects.py
class AdrStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    AFTER_REVIEW = "after_review"
    PROPOSED = "proposed"
    REVIEW_FAILED = "review_failed"
```

Command methods enforce guards:

| Method | From | To | Guard |
|--------|------|-----|-------|
| `complete_review(result, reviewed_at)` | `in_review` | `after_review` | `AdrInvalidReviewStatus` if not `in_review` |
| `fail_review(kind, message, updated_at)` | `in_review` | `review_failed` | same |
| `publish(updated_at)` | `after_review` | `proposed` | `AdrInvalidPublishStatus` — **user-initiated only** |

```182:194:backend/domain/adr/aggregate.py
    def complete_review(self, result: ReviewResult, reviewed_at: datetime) -> Self:
        """Record successful AI review; requires ``in_review``."""
        if self.status != AdrStatus.IN_REVIEW:
            raise AdrInvalidReviewStatus()
        return self._with_review_completed(result=result, reviewed_at=reviewed_at)

    def fail_review(self, kind: str, message: str, updated_at: datetime) -> Self:
        """Record failed AI review; requires ``in_review``."""
        if self.status != AdrStatus.IN_REVIEW:
            raise AdrInvalidReviewStatus()
        return self._with_review_failed(
            kind=kind, message=message, updated_at=updated_at
        )
```

`_with_review_completed` sets `review_result`, clears `review_error`, and moves to `after_review`. `_with_review_failed` sets `review_error`, clears `review_result`, and moves to `review_failed`. **No validation of rating quality or annotation actionability occurs in the domain** — any structurally valid `ReviewResult` completes.

Post-review user decisions are explicit: only `publish()` from `after_review` advances to `proposed`. Ratings do not auto-publish or auto-reject.

### Application layer — ratings delivered; validation is logs-only

`AdrReviewService.review_adr` runs a three-phase pipeline (static gaps → parallel per-section LLM ratings → cross-section annotations), merges via `merge_review_results`, then validates:

```113:120:backend/application/services/adr_review_service.py
        validation = validate_review_result(markdown, result)
        if not validation.passed:
            _logger.warning(
                "adr_review.validation_failed",
                failures=validation.failures,
            )

        return result
```

Validation failures **never raise** and **never block** `after_review`. Tests confirm invalid merged results still emit `AIReviewCompleted` (`test_run_ai_review_completes_when_merged_result_fails_validation`).

`RunAiReviewHandler` branches:

- LLM / provider / worker exceptions → `_fail_review` → `review_failed`
- Successful merge → `_complete_review` → `after_review`

```60:88:backend/application/handlers/run_ai_review.py
        try:
            ...
            result = await self._adr_review_service.review_adr(markdown)
        except (RetryableInternalError, InternalError) as exc:
            await self._fail_review(stored_event, adr_id, exc)
            ...
            return
        except Exception as exc:
            retryable = RetryableInternalError(str(exc))
            await self._fail_review(stored_event, adr_id, retryable)
            ...
            return

        ...
        await self._complete_review(stored_event, adr_id, result)
```

Infrastructure `kind` values (`retryable_internal_error`, `internal_error`) flow from exception classes to `AIReviewFailed` and projection `review_error.kind`.

### Projection layer — status always changes on outcome

```64:103:backend/infrastructure/adapters/persistence/projections/adr_projection.py
    async def apply_review_result(...):
        # status → after_review, review_annotations populated, review_error cleared

    async def record_review_failure(...):
        # status → review_failed, review_error populated with kind
```

Migration `004_review_failed_status` backfilled legacy rows that were `in_review` + non-null `review_error` to `review_failed`.

### Frontend — user decides after `after_review`; legacy polling path remains

Editor lock applies only to `in_review` (not `review_failed` or `after_review`):

```27:38:frontend/app/pages/workspace/adr/[id].vue
const isEditorDisabled = computed(
  () =>
    adr.currentAdr.value?.status === "in_review" ||
    ...
);
const showPublishButton = computed(
  () => adr.currentAdr.value?.status === "after_review",
);
```

Publish is shown only in `after_review` — ratings and annotations inform edits; the user clicks Publish when ready.

**Legacy polling behavior** still handles `in_review` + `review_error`:

```6:10:frontend/app/composables/useAdrReviewPolling.ts
function isReviewPending(
  adr: { status: string; reviewError: unknown } | null | undefined,
): boolean {
  return adr?.status === "in_review" && adr.reviewError === null;
}
```

Lines 72–75 stop polling when `reviewError` appears while still `in_review`. With the shipped backend this combination should not occur for new reviews; it is a **pre-`review_failed` artifact**. Frontend tests (`adr-review-polling.test.ts`, `adr-editor-page.test.ts`) still seed `in_review` + `validation_failed` scenarios.

### Gaps vs the invariant

| Gap | Severity | Notes |
|-----|----------|-------|
| Handler skip `adr_not_found` | Medium | Submit already set projection to `in_review`; handler marks event processed without outcome → stranded `in_review` |
| Worker crash before `_complete_review` / `_fail_review` persist | Low | Event replay on startup may recover; no domain timeout |
| No retry from `in_review` | By design | `retry_review` requires `review_failed`; `submit_for_review` requires `draft` |
| Frontend `in_review` + `review_error` handling | Cleanup | Should assume `review_failed` instead |
| Event replay without status guards | Low | `ADR.restore` applies outcomes without checking current status — corrupt streams only |
| Stale docs (roadmap R-01 outcome, S-09 prerequisite) | Docs | R-01 strict-validation outcome partially reversed by error-status |

## Code References

- `backend/domain/adr/value_objects.py:10-15` — status enum
- `backend/domain/adr/aggregate.py:182-233` — `complete_review`, `fail_review`, private transitions
- `backend/domain/adr/events.py:30-39` — `AIReviewCompleted`, `AIReviewFailed`
- `backend/application/services/adr_review_service.py:103-120` — merge + logs-only validation
- `backend/application/handlers/run_ai_review.py:44-226` — handler orchestration, skip reasons, complete/fail paths
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py:36-103` — projection writes
- `backend/infrastructure/adapters/persistence/migrations/versions/004_review_failed_status.py` — legacy backfill
- `frontend/app/pages/workspace/adr/[id].vue:27-63` — editor lock, publish button, review panel
- `frontend/app/composables/useAdrReviewPolling.ts:6-75` — polling + legacy `in_review`+`review_error` stop
- `backend/tests/application/handlers/test_run_ai_review.py:236-268` — validation failure still completes
- `backend/tests/domain/test_adr_aggregate.py:216-347` — domain transition guards

## Architecture Insights

1. **Separation of concerns**: Domain enforces *when* status changes; application decides *success vs infrastructure failure*; validation quality is observability-only after error-status.
2. **User agency after review**: Ratings (0–5 per section, including score-0 for missing sections) and annotations are informational. The only automatic post-review transition is handler-driven `in_review` → `after_review`. Publishing is always user-initiated.
3. **Infrastructure errors are a distinct branch**: `review_failed` unlocks editing and optional retry (`POST /api/adrs/{id}/retry-review`). This matches the user's "error when problems are at the infrastructure level" requirement.
4. **Lessons apply**: Use typed domain errors (`AdrInvalidReviewStatus`, etc.); keep transition helpers private (`_with_*`); prefer `TaskGroup` for parallel LLM calls.

## Historical Context (from prior changes)

| Change | Path | Relevance |
|--------|------|-----------|
| S-04 | `context/archive/2026-06-17-first-ai-review-annotations/` | Original design: failure stayed `in_review` + `review_error` |
| S-07 | `context/archive/2026-06-19-review-validation-logs-only/` | Planned logs-only validation → `after_review`; **never implemented** |
| R-01 | `context/archive/2026-06-26-adr-validation-re-shape/` | Introduced ratings; **strict validation blocked `after_review`** |
| error-status | `context/archive/2026-07-04-error-status/` | **Shipped the target model**: soft validation + `review_failed` + retry |
| conditional-adr-re-review | `context/changes/conditional-adr-re-review/` | S-09; stale S-07 prerequisite note |

Key quote from error-status plan:

> "When the review pipeline produces a merged result (even if merge validation would previously have failed), the ADR completes to `after_review` with section ratings and annotations — the user decides whether to edit or publish."

PRD (`context/foundation/prd.md:153`) reflects this as current product truth.

## Related Research

- `context/archive/2026-07-04-error-status/research.md` — stuck `in_review` analysis and recommended `review_failed` status
- `context/archive/2026-06-26-adr-validation-re-shape/research.md` — ratings pipeline and strict-validation era
- `context/changes/conditional-adr-re-review/research.md` — re-review eligibility (downstream of `after_review`)

## Recommended Scope for `/plan`

Given the invariant is largely implemented, plan phases should focus on:

1. **Contract tests / documentation** — assert and document: every successful handler run ends `in_review` in `after_review` or `review_failed`; no code path raises on merge validation.
2. **Frontend cleanup** — remove or refactor `in_review` + `review_error` polling/UI assumptions; update tests to use `review_failed`.
3. **Handler hardening (optional)** — decide policy for `adr_not_found` skip: fail to `review_failed` vs operational alert; consider whether crash recovery needs explicit watchdog.
4. **Doc hygiene** — update roadmap R-01 outcome text, S-09 prerequisite, conditional-adr-re-review stale references.

## Open Questions

1. Should `adr_not_found` handler skip transition to `review_failed` (internal_error) instead of leaving `in_review`?
2. Should frontend tests that use `code: "validation_failed"` on `in_review` rows be deleted or migrated to `review_failed` fixtures?
3. Does this change need a PRD amendment, or only test/doc alignment since error-status already amended FR-016 and the soft-validation note?
4. For S-09 conditional re-review: confirm eligibility keys off `after_review` + ratings/annotations, not annotation count alone (static gaps always produce annotations).
