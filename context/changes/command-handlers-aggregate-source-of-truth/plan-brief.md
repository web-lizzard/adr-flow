# Command Handlers — Aggregate Source of Truth — Plan Brief

> Full plan: `context/changes/command-handlers-aggregate-source-of-truth/plan.md`
> Research: `context/changes/command-handlers-aggregate-source-of-truth/research.md`

## What & Why

Command handlers and `RunAiReviewHandler` today read projection tables to decide state changes, while the event store is only a write log. That spreads business rules across handlers and SQL projectors. This change makes the **event stream** the write-path source of truth: rehydrate aggregates via `load_stream`, call aggregate command methods with **value-object inputs**, then **handlers create events** and update sync projections in the same transaction.

## Starting Point

Phases 1–2 delivered `load_stream`, `rehydrate_adr`, rich `ADR`/`User` aggregates, advisory locking, and refactored command handlers. `RunAiReviewHandler` still reads `AdrRepository` for idempotency and status guards before/after the LLM call.

## Desired End State

All write paths (commands + async AI review) follow the same pattern: `lock_aggregate` → `load_stream` → `rehydrate_adr` → aggregate command method → handler builds event → `append` → sync projection. `AdrRepository` is query-only. Pre-flight stream load before the LLM preserves skip logic without holding the advisory lock during external calls.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Aggregate scope | ADR + User commands; ADR review in Phase 3 | Completes write-path consistency | Plan |
| Aggregate inputs | Value objects only; no events into aggregates | Events are persistence artifacts | User |
| Event creation | Handlers build events after aggregate transitions | Keeps aggregates free of event types | User |
| Rehydration | `rehydrate.py` maps event payloads → VOs → transition helpers | Events parsed at boundary only | Plan |
| RunAiReviewHandler | Phase 3 — stream-load + `complete_review` / `fail_review` | User request; closes projection-first gap on async path | User |
| Idempotency (review) | Stream scan for `after_review` and duplicate `AIReviewFailed` | `ReviewError` VO lacks `source_event_id`; stream is authoritative | Plan |
| LLM transaction | Pre-flight read without lock; lock only on persist | Avoid holding DB lock during LLM latency | Plan |
| Sync projections | Keep imperative SQL in write txn | Async projection subscribers out of scope | Plan |

## Scope

**In scope (Phase 3):**

- `ADR.complete_review`, `ADR.fail_review` command methods
- Refactor `backend/application/handlers/run_ai_review.py`
- Update `test_run_ai_review.py` to stream-based fakes
- Full lifecycle integration tests + manual smoke

**Out of scope:**

- Async projection subscribers
- Sync projector refactor to call transition helpers
- Stream versioning, `ADRSoftDeleted` handler, frontend

## Architecture / Approach

```
RunAiReviewHandler:
  pre-flight: load_stream → rehydrate_adr → skip if after_review / duplicate failure
  LLM review (no lock)
  persist UoW:
    lock_aggregate → load_stream → rehydrate_adr
    → adr.complete_review(result, reviewed_at)
    → handler builds AIReviewCompleted
    → append → apply_review_result → mark_processed
```

## Phases at a Glance

| Phase | What it delivers | Status |
| ----- | ---------------- | ------ |
| 1. Domain & EventStore | `load_stream`, aggregates, rehydrators | Done |
| 2. Commands + UoW lock | All 5 command handlers refactored | Done |
| 3. AI review + integration | `RunAiReviewHandler` stream-load, E2E verification | **Next** |

**Estimated effort (Phase 3):** ~1 focused session

## Open Risks & Assumptions

- Duplicate-failure idempotency moves from projection `review_error.source_event_id` to scanning the event stream for `AIReviewFailed.source_event_id`.
- Pre-flight and persist loads must both re-check guards to close races between concurrent replays.

## Success Criteria (Summary)

- `RunAiReviewHandler` has no `AdrRepository` dependency
- Existing `test_run_ai_review.py` scenarios pass with stream fakes
- Full ADR lifecycle works manually through AI review to publish
