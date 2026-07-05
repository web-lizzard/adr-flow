# Error Status — Plan Brief

> Full plan: `context/changes/error-status/plan.md`
> Research: `context/changes/error-status/research.md`

## What & Why

Failed AI reviews currently leave ADRs stuck in `in_review` with no way to edit, resubmit, or understand what to do next. We introduce `review_failed` as a fifth lifecycle status for system-level failures, a dedicated retry command/endpoint, and structured error UX with `required_action` guidance. Merge-validation issues no longer block the pipeline — reviews complete to `after_review` with ratings so the user decides next steps.

## Starting Point

`fail_review` keeps status at `in_review`; projection writes only `review_error`. `submit_for_review` accepts `draft` only. `RunAiReviewHandler` labels all failures `validation_failed`. Frontend stops polling on error but still shows “In review” with a locked editor and message-only error display. R-01 restored strict merge validation that strands users despite available ratings.

## Desired End State

System failures land in `review_failed` with `internal_error`, persisted `required_action`, a red badge, unlocked editor, and “Try again” when actionable. Retry via `POST /api/adrs/{id}/retry-review` emits a fresh submit event and re-runs the review. Reviews that produce a merged result (even with validation warnings) complete to `after_review`. Stranded `in_review`+error rows are auto-migrated.

## Key Decisions Made

| Decision | Choice | Why | Source |
| -------- | ------ | --- | ------ |
| Fifth status name | `review_failed` | Clear terminal failure distinct from active `in_review` | Plan |
| Retry handler | New `RetryAdrForReviewCommandHandler` | Separate use case; user preference over extending submit | Plan |
| Retry endpoint | `POST /api/adrs/{id}/retry-review` | Mirrors `submit-review` conventions | Plan |
| Stranded row migration | Auto-migrate projection to `review_failed` | Unblocks existing stuck ADRs immediately | Plan |
| Retry precondition | Immediate — no edit required | Fast recovery from transient provider failures | Plan |
| `required_action` | Persisted on `review_error` (backend) | Consistent API contract for frontend CTAs | Plan |
| Error codes (new failures) | `internal_error` only for `review_failed` path | System can't deliver review — not ADR corruption | Plan |
| Provider/LLM failures | Map to `internal_error` | User decision; avoids separate `provider_failed` code | Plan |
| Merge validation failures | Complete to `after_review` with ratings | User gets recommendations and decides | Plan |
| Admin contact | Placeholder copy only | No support URL in MVP | Plan |
| List view | Status badge only | Full error detail on ADR page | Plan |

## Scope

**In scope:**
- `review_failed` status across domain, projection, API, frontend
- `required_action` on `ReviewError` / `AIReviewFailed` / API response
- `RetryAdrForReviewCommandHandler` + `POST .../retry-review`
- Handler failure taxonomy (`internal_error` + `required_action` derivation)
- Soften merge validation gate in `AdrReviewService`
- Alembic data migration for stranded rows
- Frontend badge, error panel, retry CTA, editor unlock
- PRD amendment (5 statuses)

**Out of scope:**
- Extending submit handler for retry
- `provider_failed` code
- Support email/URL for `contact_admin`
- List-level error flags/snippets
- Retry rate limiting
- Event-store historical event rewrite
- S-09 conditional re-review

## Architecture / Approach

```
draft ──submit──► in_review ──success──► after_review ──publish──► proposed
                      │                        ▲
                      │ (merge result,         │ (even if validation
                      │  incl. soft-fail)      │  warnings logged)
                      └────────────────────────┘
                      │
                      └──system fail──► review_failed ──retry──► in_review
```

New retry flow mirrors submit: command handler → `ADRSubmittedForReview` event → `mark_in_review` projection → `RunAiReviewHandler` (fresh `source_event_id` bypasses `duplicate_failure`). Failure path sets `review_failed` in both aggregate replay and projection.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Domain & failure taxonomy | `review_failed`, `required_action`, softened validation, handler codes | Rehydration must set status on `AIReviewFailed` replay |
| 2. Retry command & API | `retry_adr_for_review` handler, endpoint, migration | Migration must backfill `required_action` on legacy JSON |
| 3. Frontend error UX | Badge, panel, retry CTA, polling | Stale `in_review` copy if status checks incomplete |
| 4. PRD & docs | Product alignment | PRD contradictions if non-goal not updated |

**Prerequisites:** Existing submit/review pipeline (S-04+), Alembic migrations, frontend review polling
**Estimated effort:** ~2-3 focused sessions across 4 phases

## Open Risks & Assumptions

- Softening merge validation reverses part of R-01 — intentional per user direction; monitor review quality in `after_review`
- Historical `AIReviewFailed` events lack `required_action` — rehydration defaults to `retry`
- `validation_failed` code may remain on legacy migrated rows until normalized to `internal_error` in migration
- Placeholder admin copy may need a real support channel post-MVP

## Success Criteria (Summary)

- System review failure → `review_failed` with actionable error panel (not stuck “In review”)
- User can retry immediately via new endpoint; review re-queues successfully
- Merge validation warnings → `after_review` with ratings, not pipeline failure
- Stranded ADRs auto-migrated and recoverable
