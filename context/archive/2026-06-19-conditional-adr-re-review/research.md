---
date: 2026-06-19T01:47:56+00:00
researcher: Composer
git_commit: 89d7742fe276303916c463abb9bd479e4fa6a5da
branch: main
repository: adr-flow
topic: "S-09 conditional-adr-re-review — one user-requested re-review when first review reported errors"
tags: [research, codebase, s-09, re-review, adr-lifecycle, submit-for-review, run-ai-review]
status: complete
last_updated: 2026-06-19
last_updated_by: Composer
---

# Research: S-09 Conditional ADR Re-Review

**Date**: 2026-06-19T01:47:56+00:00
**Researcher**: Composer
**Git Commit**: `89d7742fe276303916c463abb9bd479e4fa6a5da`
**Branch**: main
**Repository**: adr-flow

## Research Question

What must change to implement S-09 (`conditional-adr-re-review`): let users request **one additional** AI review when the first review reported errors (non-empty actionable annotations), at most once per ADR, while edits in `after_review` still do not auto-trigger review?

## Summary

S-09 is a deliberate, minimal carve-out from the original “review once” MVP. The codebase today **structurally blocks** re-review at three layers: the aggregate accepts `submit_for_review` only from `draft`, `RunAiReviewHandler` skips when status is already `after_review`, and the frontend exposes “Publish for review” only on `draft`. The good news: the event model already supports a second cycle — a second `ADRSubmittedForReview` folds back to `in_review` and clears review fields, and `mark_in_review` in the projection mirrors that. No new event type is strictly required.

Implementation spans backend domain guards (eligibility + once-per-ADR quota), handler idempotency rewrite, a new or extended API route, and frontend “Request re-review” UI. **S-07** (`review-validation-logs-only`) is a prerequisite so users always see first-review output before deciding to re-review; it is planned but not yet shipped at research time.

Open product questions remain: PRD wording (FR-008 “exactly once”, non-goal “No re-review”), trigger status (`after_review` only vs also `proposed`), and the precise definition of “errors” (roadmap: non-empty actionable annotations).

## Detailed Findings

### Product rules (S-09 vs original MVP)

| Rule | Original PRD / delivered code | S-09 (roadmap) |
|------|------------------------------|----------------|
| Edits in `after_review` | Never auto-trigger review | **Unchanged** |
| Publish to `proposed` | Never triggers review | **Unchanged** (FR-009) |
| Initial review | Once, from `draft` via “Publish for review” | **Unchanged** |
| Conditional re-review | Not allowed; deferred post-MVP | **One** user-requested re-review when first review had **errors** |
| Quota | N/A | **At most once per ADR** for this exception |
| Unlimited / quota-based re-review | Parked | **Still parked** |

Source: `context/foundation/roadmap.md:195-207`, `context/foundation/prd.md:103-106,168`.

### Current ADR lifecycle (domain)

| Method | From | To | Guard |
|--------|------|-----|-------|
| `submit_for_review` | `draft` | `in_review` | `status != DRAFT` → `AdrInvalidSubmitStatus` |
| `complete_review` | `in_review` | `after_review` | `status != IN_REVIEW` → `AdrInvalidReviewStatus` |
| `publish` | `after_review` | `proposed` | `status != AFTER_REVIEW` → `AdrInvalidPublishStatus` |

`submit_for_review` and `_with_submitted_for_review` already clear `review_result`, `review_error`, and `reviewed_at` when entering a new review cycle — correct semantics for a second submit:

```162:200:backend/domain/adr/aggregate.py
    def submit_for_review(self, updated_at: datetime) -> Self:
        """Move from ``draft`` to ``in_review``; clears review fields."""
        if self.status != AdrStatus.DRAFT:
            raise AdrInvalidSubmitStatus()
        return self._with_submitted_for_review(updated_at)
    ...
    def _with_submitted_for_review(self, updated_at: datetime) -> Self:
        return replace(
            self,
            status=AdrStatus.IN_REVIEW,
            review_result=None,
            review_error=None,
            reviewed_at=None,
            updated_at=updated_at,
        )
```

`restore()` folds `ADRSubmittedForReview` through the same helper (`aggregate.py:114-118`), so append-only event history supports re-review without a new event type.

`update_content` / `update_title` allow `after_review` and preserve `review_result` — no change needed for “edits don’t auto-trigger review” (`aggregate.py:150-160`; tests at `backend/tests/domain/test_adr_aggregate.py:110-156`).

### Blocker 1: Submit command — draft only

`SubmitAdrForReviewCommandHandler` delegates directly to `adr.submit_for_review()` with no additional guards:

```56:73:backend/application/commands/submit_adr_for_review.py
            updated_at = datetime.now(UTC)
            new_adr = adr.submit_for_review(updated_at)
            event = ADRSubmittedForReview(
                adr_id=AdrId(command.adr_id),
                user_id=UserId(command.user_id),
                content=new_adr.content,
                occurred_at=updated_at,
            )
            ...
            await uow.adr_projection.mark_in_review(
                command.adr_id,
                updated_at=updated_at,
            )
```

API: `POST /api/adrs/{adr_id}/submit-review` returns 202 (`backend/infrastructure/api/routers/adr.py:73-113`). `DomainError` → 400.

### Blocker 2: RunAiReviewHandler — skip when already after_review

```146:166:backend/application/handlers/run_ai_review.py
    def _skip_reason(
        self,
        stored_event: StoredEvent,
        stored_events: list[StoredEvent],
    ) -> str | None:
        ...
        if adr.status == AdrStatus.AFTER_REVIEW:
            return "already_reviewed"
        if any(
            isinstance(stored.event, AIReviewFailed)
            and stored.event.source_event_id == stored_event.id
            for stored in stored_events
        ):
            return "duplicate_failure"
        return None
```

After a valid second submit, ADR is `in_review` so this branch does not fire. The skip logic must become **per-submit-event** idempotent (e.g. skip only if this `ADRSubmittedForReview` already has a matching `AIReviewCompleted`/`AIReviewFailed`), not global `after_review` status. The `duplicate_failure` pattern (keyed on `source_event_id`) is the right model.

Test: `test_run_ai_review_is_idempotent_when_adr_already_after_review` (`backend/tests/application/handlers/test_run_ai_review.py`).

### Blocker 3: No re-review quota tracking

No `re_review_count`, `re_review_used`, or similar field exists in:

- Aggregate (`aggregate.py:44-54`)
- Domain events (`backend/domain/adr/events.py`)
- `adrs` table (`backend/infrastructure/adapters/persistence/models.py:48-69`)

**Options for “at most once per ADR”:**

1. Count `ADRSubmittedForReview` events in the stream (`>= 2` ⇒ quota consumed)
2. Add `re_review_used: bool` on aggregate + optional projection column
3. New event metadata (e.g. `is_re_review: bool` on submit)

Eligibility for re-review must be checked **before** the second submit clears `review_result`, or derived from event history (first `AIReviewCompleted` had non-empty annotations).

### Detecting “first review reported errors”

`ReviewResult` shape (`backend/domain/adr/value_objects.py:66-71`):

```python
annotations: tuple[ReviewAnnotation, ...]
reviewed_at: datetime
reviewed_content: str | None = None
```

**Practical eligibility check before second submit:**

```python
adr.review_result is not None and len(adr.review_result.annotations) > 0
```

- Clean first review: `annotations=()` — user should Publish, not re-review.
- **Not the same as `AIReviewFailed`:** `fail_review` leaves status `in_review`, sets `review_error`, clears `review_result`. S-09 targets successful reviews that still list issues.

After a second `AIReviewCompleted`, `review_result` is **replaced** — first-review eligibility cannot be inferred from current aggregate state post–second review.

`GetAdrReviewStatusQueryHandler` exposes `annotation_counts` by kind (`backend/application/queries/get_adr_review_status.py`) — useful for API/UI polling, not a dedicated eligibility flag.

### Domain errors — existing and likely new

Existing lifecycle errors (`backend/domain/errors.py:54-71`):

- `AdrInvalidSubmitStatus` — “ADR can only be submitted from draft status”
- `AdrInvalidReviewStatus`, `AdrInvalidPublishStatus`, `AdrEditWhileInReview`

Likely **new** errors per `context/foundation/lessons.md` (dedicated types, not bare `DomainError`):

| Error | When |
|-------|------|
| `AdrReReviewNotEligible` | Wrong status; first review had empty annotations |
| `AdrReReviewAlreadyUsed` | Second re-review attempt exceeds once-per-ADR quota |

### Events, projections, and schema

**Review events** (`backend/domain/adr/events.py`):

| Event | Payload |
|-------|---------|
| `ADRSubmittedForReview` | `adr_id`, `user_id`, `content` |
| `AIReviewCompleted` | `adr_id`, `review_result` |
| `AIReviewFailed` | `adr_id`, `source_event_id`, `code`, `message` |

**Projection methods** (`backend/infrastructure/adapters/persistence/projections/adr_projection.py`):

| Method | Effect |
|--------|--------|
| `mark_in_review` | `status=in_review`, clears `review_annotations`, `reviewed_at`, `review_error` |
| `apply_review_result` | `status=after_review`, sets `review_annotations`, `reviewed_at`, clears `review_error` |
| `mark_proposed` | `status=proposed` — **preserves** review columns |

`mark_in_review` clearing behavior is correct for starting a new review cycle; publish intentionally preserves annotations (asymmetric with submit — documented in `context/changes/command-handlers-aggregate-source-of-truth/research.md:190-198`).

DB column is `review_annotations` (JSONB), not `review_result`. `review_error` stores LLM/validation failure metadata while stuck in `in_review`.

### Frontend — current state and gaps

**“Publish for review”** — `draft` only (`frontend/app/pages/workspace/adr/[id].vue`):

- `showSubmitButton` when `status === "draft"`
- Handler: save-if-dirty → `adr.submitForReview()` → `POST /adrs/{id}/submit-review`

**“Publish”** — `after_review` only; no re-review button exists.

**Reusable for S-09:**

- `in_review` lock UX, `useAdrReviewPolling`, `AdrReviewAnnotations` panel
- Submit pattern: save → POST → reload → poll

**Missing (greenfield):**

1. API client — no `requestReReview` in `frontend/composables/useApi.ts`
2. Store method — no `requestReReview` in `frontend/app/stores/adr.ts`
3. Editor page — `showReReviewButton`, `onRequestReReview`, loading/error state
4. Types — no `re_review_available` / `re_review_used` on `AdrResponse`

**Conditional visibility (product TBD):**

- `after_review` + `(reviewAnnotations?.length ?? 0) > 0`
- Hide when quota consumed (needs backend field)
- Coexist with Publish button in `after_review`

### Prerequisite: S-07

S-07 (`review-validation-logs-only`) ensures users always reach `after_review` with LLM output even when quality checks fail. Without it, ADRs can remain stuck in `in_review` with `review_error`, never reaching the state where S-09 eligibility applies. See `context/changes/review-validation-logs-only/research.md`.

## Code References

- `backend/domain/adr/aggregate.py:162-200` — `submit_for_review` draft-only guard and review-field clearing
- `backend/application/commands/submit_adr_for_review.py:56-73` — submit command path
- `backend/application/handlers/run_ai_review.py:146-166` — `_skip_reason` / `already_reviewed`
- `backend/domain/errors.py:59-61` — `AdrInvalidSubmitStatus` message
- `backend/domain/adr/value_objects.py:66-71` — `ReviewResult` / annotation eligibility
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py:36-81` — `mark_in_review`, `apply_review_result`
- `backend/infrastructure/api/routers/adr.py:73-113` — submit-review route
- `frontend/app/pages/workspace/adr/[id].vue` — editor status gates and buttons
- `frontend/composables/useApi.ts:104-118` — review API client
- `backend/tests/domain/test_adr_aggregate.py:86-90` — draft-only submit test
- `backend/tests/application/handlers/test_run_ai_review.py` — idempotency when `after_review`

## Architecture Insights

1. **Invariant loosening, not migration** — persistence-scaffold research established that “review runs once” is an aggregate invariant, not a schema limit (`context/archive/2026-06-14-persistence-scaffold/research.md:158`). S-09 is a code change.

2. **Event-fold model** — command-handlers research recommends re-review via append-only second `ADRSubmittedForReview` + `AIReviewCompleted`; old review stays in event history; aggregate holds latest fold (`context/changes/command-handlers-aggregate-source-of-truth/research.md:204-227`). Aggregate rehydration (delivered in command-handlers work) directly supports this.

3. **Per-submit idempotency** — replace global `after_review` skip with event-pair checks (`source_event_id` pattern from `AIReviewFailed`).

4. **Dedicated domain errors** — follow `lessons.md`: no bare `DomainError` for lifecycle violations.

5. **Minimal public API** — prefer `submit_for_re_review()` or extended `submit_for_review()` with preconditions in command method, not public `_with_*` helpers.

## Historical Context (from prior changes)

| Source | Insight |
|--------|---------|
| `context/foundation/roadmap.md:195-207` | S-09 outcome, prerequisites (S-07, S-05), open questions, risks |
| `context/foundation/prd.md:103-106,168` | FR-008 “exactly once”, FR-009 no auto re-review on publish, non-goal “No re-review after edits” |
| `context/archive/2026-06-18-publish-after-review/research.md` | Re-review “structurally impossible” pre-S-09; edit-without-re-review already works |
| `context/archive/2026-06-14-persistence-scaffold/research.md` | Forward-only machine; embed review in ADR aggregate; split `Review` aggregate only for independent lifecycle |
| `context/changes/command-handlers-aggregate-source-of-truth/research.md:204-233` | Implementation blueprint: second submit, annotation clearing, handler idempotency, event fold |

**Evolution:**

```
PRD (2026-06-08)     → review once, no re-review on edits
persistence-scaffold → invariant in aggregate, re-review parked
S-04 / S-05          → delivered no-re-review loop; re-review blocked in code
roadmap v1 (2026-06-19) → S-09 proposed as narrow exception
```

## Implementation Touchpoint Summary

| Layer | File | S-09 change |
|-------|------|-------------|
| Domain | `backend/domain/adr/aggregate.py` | New/extended submit method; eligibility + quota guards |
| Errors | `backend/domain/errors.py` | `AdrReReviewNotEligible`, `AdrReReviewAlreadyUsed` |
| Command | `submit_adr_for_review.py` or new `request_adr_re_review.py` | Pre-check eligibility; emit `ADRSubmittedForReview` |
| Handler | `run_ai_review.py` | Per-submit `_skip_reason`; remove global `already_reviewed` |
| Projection | `adr_projection.py` | `mark_in_review` likely unchanged |
| API | `routers/adr.py` | New route or extend submit-review; map new errors |
| Query | `get_adr_review_status.py` / ADR read model | Optional `re_review_available` flag for UI |
| Frontend | `useApi.ts`, `adr.ts`, `[id].vue` | Request re-review button, store method, types |
| Tests | aggregate, command, handler, API, frontend | Re-review happy path + rejection cases |

## Related Research

- `context/changes/review-validation-logs-only/research.md` — S-07 prerequisite
- `context/changes/command-handlers-aggregate-source-of-truth/research.md` — re-review event-fold blueprint
- `context/archive/2026-06-18-publish-after-review/research.md` — S-05 baseline (edit/publish without re-review)
- `context/archive/2026-06-14-persistence-scaffold/research.md` — original “review once” invariant

## Open Questions

| # | Question | Owner | Blocks `/plan`? |
|---|----------|-------|-----------------|
| 1 | Update PRD FR-008 (“exactly once”) and non-goal “No re-review” for S-09 exception? | User | No; recommended before ship |
| 2 | Re-review trigger from `after_review` only vs also `proposed`? | User | Only if aggregate transitions differ |
| 3 | Exact “errors” definition — any annotation vs specific kinds (`missing_section` only)? | Unspecified | Needed in plan |
| 4 | Same route (`submit-review`) vs dedicated `request-re-review` endpoint? | Implementation | No |
| 5 | Expose `re_review_available` on ADR API vs client-side inference from annotations? | Implementation | No |
| 6 | Success criterion “one AI review iteration” (`prd.md:35`) — update metrics/copy? | User | No |

## Recommended Planning Sequence

1. Resolve open questions 1–3 (user decisions).
2. Ship or plan **S-07** first — S-09 depends on users reliably reaching `after_review`.
3. Backend: domain guards → command → handler idempotency → API → tests.
4. Frontend: API client → store → editor button (conditional visibility).
5. PRD update (FR-008 exception, clarify non-goal scope) before ship.
