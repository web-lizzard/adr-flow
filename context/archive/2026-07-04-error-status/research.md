---
date: 2026-07-05T00:06:00+02:00
researcher: Composer
git_commit: 8c0961eb28a96fd238f8e8b540a73fafeaf2f4a7
branch: main
repository: adr-flow
topic: "Error status for failed AI reviews — retryable state and frontend error UX"
tags: [research, codebase, review-error, in_review, adr-status, frontend]
status: complete
last_updated: 2026-07-05
last_updated_by: Composer
---

# Research: Error status for failed AI reviews — retryable state and frontend error UX

**Date**: 2026-07-05T00:06:00+02:00
**Researcher**: Composer
**Git Commit**: `8c0961eb28a96fd238f8e8b540a73fafeaf2f4a7`
**Branch**: main
**Repository**: adr-flow

## Research Question

A review shouldn't be stuck in the `in_review` status when an error occurs. Prefer a new status that allows the review to be retried. On the front end, add information about the reason for the error and the required action (contacting an administrator or trying again sooner).

## Summary

**Today, failed AI reviews leave the ADR in `in_review` with `review_error` populated.** The domain `fail_review` method does not change status; the projection `record_review_failure` writes only `review_error`. The user cannot edit (`AdrEditWhileInReview`), cannot resubmit (`submit_for_review` accepts only `draft`), and the handler will not re-run the LLM for the same submit event (`duplicate_failure` idempotency). The frontend stops polling when `review_error` appears but still shows “In review”, keeps the editor locked, and surfaces only `reviewError.message` with no retry or admin guidance.

**The user's goal aligns with a gap the team has documented since S-04** — `review_error` was meant to make failure recoverable, but resubmit UX was never shipped. R-01 (`adr-validation-re-shape`) superseded S-07 and restored strict validation failures that strand users in `in_review`.

**Recommended direction for `/plan`:**

1. **Introduce a fifth lifecycle status** (e.g. `review_failed`) emitted on `AIReviewFailed`, distinct from active `in_review`. This conflicts with PRD non-goal “4 statuses only” but matches `test-plan.md` risk #6 (“transitions to an error state”) and the user's explicit preference.
2. **Allow retry from `review_failed`** via a new command (e.g. `retry_review` → `in_review` + new `ADRSubmittedForReview`) or by extending `submit_for_review` to accept `review_failed` after edits.
3. **Extend `review_error` (or parallel fields) with `required_action`** (`retry` | `contact_admin`) and stable `code` values (`validation_failed`, `provider_failed`, `internal_error`) so the frontend can branch copy and CTAs.
4. **Frontend:** new badge, unlock editor on `review_failed`, show structured error panel with reason + action, expose “Try again” when `required_action === retry`.

## Detailed Findings

### Current status model (four statuses)

| Status | Meaning |
|--------|---------|
| `draft` | Editable; user can submit for review |
| `in_review` | Review in progress; editing blocked |
| `after_review` | Review complete; user can edit and publish |
| `proposed` | Published |

Defined in `backend/domain/adr/value_objects.py:10-14`. Frontend badge map in `frontend/app/components/adr/AdrStatusBadge.vue:8-25` — no error variant.

### Failure path: status stays `in_review`

**Domain aggregate** — `fail_review` requires `in_review` but `_with_review_failed` does not change status:

```214:219:backend/domain/adr/aggregate.py
    def _with_review_failed(self, code: str, message: str) -> Self:
        return replace(
            self,
            review_result=None,
            review_error=ReviewError(code=code, message=message),
        )
```

Contrast `complete_review` → `_with_review_completed` sets `status=AFTER_REVIEW` and clears `review_error`.

**Event** — `AIReviewFailed` carries `source_event_id`, `code`, `message` (`backend/domain/adr/events.py:32-36`).

**Handler** — `RunAiReviewHandler._fail_review` always uses `code = "validation_failed"` even for provider/LLM exceptions (`backend/application/handlers/run_ai_review.py:166-167`). It appends `AIReviewFailed` and calls `record_review_failure`.

**Projection** — `record_review_failure` updates `review_error` JSON only; **status column unchanged** (`backend/infrastructure/adapters/persistence/projections/adr_projection.py:83-102`).

### Failure sources (all converge to same stuck state)

| Source | Where raised | Handler | Final status | User recovery |
|--------|--------------|---------|--------------|---------------|
| Per-section LLM exhaustion (2 attempts) | `AdrReviewService._complete_with_retry` | `_fail_review` | `in_review` | None |
| Merge validation failure | `AdrReviewService.review_adr:111-120` | `_fail_review` | `in_review` | None |
| Any other exception | Handler `except Exception` | `_fail_review` | `in_review` | None |

Service-layer per-call retries exist; handler-level retry was removed in R-01.

### Idempotency blocks automatic retry

`_skip_reason` returns `duplicate_failure` when an `AIReviewFailed` already exists for the submit event's `source_event_id` (`backend/application/handlers/run_ai_review.py:98-103`). The handler marks the submit event processed without re-invoking the LLM.

### Submit API: draft-only, no retry endpoint

- `submit_for_review` raises `AdrInvalidSubmitStatus` unless status is `draft` (`backend/domain/adr/aggregate.py:162-166`).
- `mark_in_review` clears `review_error` on a fresh submit (`adr_projection.py:36-47`) — infrastructure for retry exists if submit were allowed from a failure state.
- No `POST .../retry-review` or equivalent in the API router.

### API surface for errors

`ReviewErrorResponse` exposes `source_event_id`, `code`, `message`, `failed_at` (`backend/infrastructure/api/schemas/adr.py:55-68`). No `required_action` or human-facing `reason` field today.

Returned on `GET /api/adrs/{id}/review-status` and full ADR GET. Integration test `test_review_status_exposes_failure_metadata_after_invalid_review` expects `status == "in_review"` with `review_error.code == "validation_failed"` (`backend/tests/infrastructure/api/test_adr_api.py:471-532`).

### Frontend behavior on failure

**Polling** — `isReviewPending` is true only when `status === "in_review"` **and** `reviewError === null` (`frontend/app/composables/useAdrReviewPolling.ts:6-9`). Polling stops when `review_error` appears (`:72-75`).

**Editor lock** — disabled whenever `status === "in_review"`, regardless of `reviewError` (`frontend/app/pages/workspace/adr/[id].vue:25-30`). Persistence also blocks saves in `in_review` (`useAdrPersistence.ts`).

**Messaging** — Page copy says “This ADR is being reviewed and cannot be edited” for all `in_review` ADRs, including failed ones (`[id].vue:228-234`). Badge still reads “In review” (`AdrStatusBadge.vue:13-16`).

**Error display** — `AdrReviewAnnotations.vue:54-61` shows “Review failed” + `reviewError.message` only. `code`, `failed_at`, and `source_event_id` are typed in `useApi.ts` but unused in UI. No retry button, no admin contact copy.

**CTAs** — “Publish for review” only when `draft` (`[id].vue:31-33`). Sidebar auto-opens on `reviewError` (`:61-87`) but offers no action.

### PRD and product tensions

**PRD line 151** (`context/foundation/prd.md:151`): failed validation → ADR remains in `in_review` with `review_error` **until the user resubmits**. Resubmit was never implemented.

**PRD non-goal line 173**: MVP has only 4 statuses. A new `review_failed` (or similar) is a deliberate PRD amendment.

**FR-005**: edit allowed in any status except `in_review`. A distinct failure status would re-enable editing without weakening the in-progress lock.

**Distinction from S-09** (`conditional-adr-re-review`): S-09 targets successful reviews with actionable annotations in `after_review`. `AIReviewFailed` is infrastructure/validation failure with no `review_result` — separate concern.

## Code References

- `backend/domain/adr/value_objects.py:10-14` — `AdrStatus` enum (4 values)
- `backend/domain/adr/value_objects.py:102-106` — `ReviewError` value object (`code`, `message`)
- `backend/domain/adr/aggregate.py:180-184,214-219` — `fail_review` / `_with_review_failed` (no status change)
- `backend/domain/adr/aggregate.py:192-200` — `submit_for_review` clears review fields, draft-only
- `backend/domain/adr/events.py:32-36` — `AIReviewFailed` event
- `backend/application/handlers/run_ai_review.py:59-74,160-219` — catch-all failure → `_fail_review`
- `backend/application/handlers/run_ai_review.py:84-104` — `duplicate_failure` skip
- `backend/application/services/adr_review_service.py:111-120` — merge validation gate
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py:36-47` — `mark_in_review` clears `review_error`
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py:83-102` — `record_review_failure` (no status update)
- `backend/infrastructure/api/schemas/adr.py:55-88` — `ReviewErrorResponse`, `ReviewStatusResponse`
- `frontend/app/composables/useAdrReviewPolling.ts:6-9,72-75` — pending = in_review without error
- `frontend/app/pages/workspace/adr/[id].vue:25-30,228-234` — editor lock and in-review copy
- `frontend/app/components/adr/AdrReviewAnnotations.vue:54-61` — error alert (message only)
- `frontend/app/components/adr/AdrStatusBadge.vue:13-16` — “In review” badge

## Architecture Insights

1. **Status is projection-derived.** New status requires: domain transition on `fail_review`, `AIReviewFailed` fold in rehydration, projection `record_review_failure` status update, API schema/OpenAPI, frontend types and badge.
2. **Retry needs a new submit event.** Idempotency keys on `source_event_id`; retry must emit a fresh `ADRSubmittedForReview` (new event id) after user action, not replay the failed one.
3. **Error taxonomy is underspecified.** All failures persist as `validation_failed`, blocking differentiated UX (transient provider error → “try again soon” vs configuration bug → “contact administrator”).
4. **`required_action` is not in the model.** Plan should add it to `ReviewError` / `ReviewErrorMetadata` / `ReviewErrorResponse` (or derive from `code` via a static map in frontend only — backend derivation is preferable for consistency).
5. **Lessons register** (`context/foundation/lessons.md`): use typed `DomainError` subclasses for illegal transitions; keep aggregate public API minimal — any new `retry_review` should be a command method with guards.

## Historical Context (from prior changes)

| Artifact | Decision |
|----------|----------|
| `context/archive/2026-06-17-first-ai-review-annotations/plan-brief.md` | **Original:** stay `in_review` with `review_error`; “recoverable without inventing a new lifecycle status.” |
| `context/changes/review-validation-logs-only/research.md` | Documents stuck-state: no edit, no resubmit, `duplicate_failure` blocks replay. S-07 would have completed to `after_review` on validation failure only. |
| `context/changes/review-validation-logs-only/change.md` | **Superseded** by R-01 — strict validation restored. |
| `context/archive/2026-06-26-adr-validation-re-shape/plan-brief.md` | **Current policy:** fail pipeline on any validation/parallel failure; **post-failure resubmit UX explicitly deferred.** |
| `context/archive/2026-06-26-adr-validation-re-shape/plan.md` | Open choice: keep `validation_failed` code or introduce `review_failed` for clarity. |
| `context/foundation/test-plan.md` | Risk #6: ADR should not stay stuck in `in_review` — “either transitions to an error state or event replays.” |
| `context/changes/conditional-adr-re-review/research.md` | `fail_review` ≠ successful review with annotations; S-09 depends on reaching `after_review`. |

## Implementation Options (for `/plan`)

### Option A — Fifth status `review_failed` (matches user request)

```
draft ──submit──► in_review ──success──► after_review ──publish──► proposed
                      │
                      └──fail──► review_failed ──retry──► in_review
```

- `fail_review` sets `status=REVIEW_FAILED` (new enum value).
- Editing allowed in `review_failed` (update `AdrEditWhileInReview` guard or rename to block only `in_review`).
- `retry_review` command: `review_failed` → `in_review`, clear `review_error`, append new `ADRSubmittedForReview`.
- Frontend: red/destructive badge, unlock editor, “Try again” CTA, action copy from `required_action`.

**Pros:** Clear UX; polling only runs in true `in_review`; list view can show failed state.
**Cons:** PRD non-goal amendment; migration for existing `in_review` + `review_error` rows.

### Option B — Stay four statuses; treat `in_review` + `review_error` as terminal failure

- No new status; branch UI on `review_error !== null` while `in_review`.
- Allow edit when `review_error` set; add resubmit from that composite state.

**Pros:** Smaller domain change; PRD line 151 literal.
**Cons:** User explicitly prefers not stuck in `in_review`; ambiguous “in review” badge; harder list/polling semantics.

### Option C — Revert to S-07 for validation only

- Validation failures complete to `after_review`; only provider errors use failure path.

**Pros:** Avoids stuck state for validation.
**Cons:** Superseded by R-01; does not address provider failures; user asked for retry status.

**Recommendation:** Option A with PRD update, plus data migration script for stranded ADRs.

### Suggested `required_action` mapping

| `code` | `required_action` | User copy (example) |
|--------|-------------------|---------------------|
| `provider_failed` | `retry` | Temporary AI service issue. Try again in a few minutes. |
| `validation_failed` | `retry` | Review could not be processed. Edit your ADR if needed, then try again. |
| `internal_error` | `contact_admin` | Something went wrong on our side. Contact an administrator if this persists. |

Derive in handler from exception type (`AdrReviewFailedError` vs generic `Exception`) instead of hardcoding `validation_failed` for all paths.

## Related Research

- `context/changes/review-validation-logs-only/research.md` — stuck-state analysis (partially historical)
- `context/changes/conditional-adr-re-review/research.md` — re-review vs `AIReviewFailed`
- `context/archive/2026-06-26-adr-validation-re-shape/research.md` — R-01 pipeline and failure semantics

## Open Questions

1. **PRD amendment:** Is a fifth status acceptable, or should the team prefer Option B to keep four statuses?
2. **Migration:** Auto-transition existing `in_review` + non-null `review_error` → `review_failed`?
3. **Retry without edit:** Can user retry immediately from `review_failed`, or must they edit first?
4. **Admin contact:** Is there a support email/URL to link, or placeholder copy only for MVP?
5. **Rate limiting:** Should `required_action: retry` include backoff/`failed_at` guidance for provider errors?
6. **Workspace list:** Should `AdrSummary` include `review_error` or a boolean `has_review_error` for list-level indicators?
