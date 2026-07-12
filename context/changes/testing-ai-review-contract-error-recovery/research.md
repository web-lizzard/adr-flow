---
date: 2026-07-05T19:30:00+02:00
researcher: Composer
git_commit: 6a31058349d84dbfc04006317a3943f4d435f2db
branch: main
repository: adr-flow
topic: "Rollout Phase 2 — AI review contract + error recovery"
tags: [research, testing, api, review, llm, retry, idempotency]
status: complete
last_updated: 2026-07-05
last_updated_by: Composer
---

# Research: Rollout Phase 2 — AI review contract + error recovery

**Date**: 2026-07-05T19:30:00+02:00
**Researcher**: Composer
**Git Commit**: 6a31058349d84dbfc04006317a3943f4d435f2db
**Branch**: main
**Repository**: adr-flow

## Research Question

Ground rollout Phase 2 of `context/foundation/test-plan.md`.

**Risks to verify:** #1 (garbage/empty section ratings), #2 (ADR stuck in `in_review` after worker failure), #5 (retry corrupts state / duplicate events).

**Risk response guidance to verify, not blindly accept:**
- **Risk #1:** prove merged API review output always has five section ratings (0–5) with valid annotations; malformed LLM payloads cannot silently complete as empty `after_review`; challenge "schema validation exists so ratings are always good"; avoid oracle copied from implementation or exact LLM wording.
- **Risk #2:** prove handler failure transitions ADR to `review_failed` with persisted `review_error`, and user retry clears error and returns to `in_review`; challenge "TaskGroup catches exceptions"; avoid happy-path-only review tests.
- **Risk #5:** prove retry from `review_failed` is idempotent; double retry or concurrent submit does not duplicate events or leave stale `review_error`; challenge "retry endpoint returns 200 so state is correct"; avoid testing only single happy retry.

**Hot-spot directories (likelihood evidence — NOT anchors):** `backend/infrastructure/llm/`, `backend/application/handlers/`, `backend/tests/review_quality/`.

**Stack:** pytest 9.x + FastAPI `TestClient` + real Postgres (`auth_client` fixture); fake LLM via `llm_provider="fake"` (`FakeLlmCompletionPort`).

## Summary

**Risk #1 — validation is advisory today.** `validate_review_result` runs in `AdrReviewService.review_adr` but only logs warnings; `RunAiReviewHandler` never calls it. Empty `section_ratings=()` can reach `after_review` — `test_invalid_review_surfaces_review_error` (`test_adr_api.py:543-602`) documents this gap. Merge via `merge_review_results` always emits five ratings when the service returns normally; default API test ADRs have all sections missing so **zero LLM calls** run and only static score-0 ratings appear. The `review_quality/` harness exercises merge + validation at service level but not through the HTTP boundary with `complete.md`.

**Risk #2 — failure path is implemented; API proof is partial.** `RunAiReviewHandler` catches `RetryableInternalError`, `InternalError`, and wraps unexpected exceptions → `AIReviewFailed` + `record_review_failure`. `AdrReviewService` TaskGroup failures propagate (not swallowed). `test_retry_review_from_review_failed_returns_202` proves fail → `review_failed` → retry → `in_review` but **does not drain after retry** or assert full recovery to `after_review`. No dedicated submit-only failure API test.

**Risk #5 — handler idempotency exists; HTTP retry is intentionally non-idempotent.** Duplicate `AIReviewFailed` for same `source_event_id` is skipped in handler (`_skip_reason`). Second `POST /retry-review` while `in_review` returns `400` (`adr_invalid_retry_status`). No API tests for double-retry, concurrent retry, or failure-event replay idempotency. Event-stream assertions are absent from API tests.

**Cheapest useful layer:** extend `backend/tests/infrastructure/api/test_adr_api.py` with monkeypatched `build_adr_review_service` / custom `LlmCompletionPort` and existing `_wait_for_review_status` / `_drain_event_bus` helpers. Use `review_quality/fixtures/complete.md` as ADR content oracle (independent of implementation strings).

**Response guidance verified:** no speculative risks; hot-spot evidence aligns with handler/service/LLM layers. One **product decision required:** should validation failure block completion (`review_failed`) or remain documented acceptance — test plan intent favors blocking.

## Detailed Findings

### End-to-end review flow

| Layer | File | Key symbols |
|-------|------|-------------|
| API submit/retry | `infrastructure/api/routers/adr.py:72-109` | `submit_adr_for_review`, `retry_adr_for_review` → 202 |
| Event handler | `application/handlers/run_ai_review.py` | `RunAiReviewHandler.handle`, `_fail_review`, `_complete_review`, `_skip_reason` |
| LLM orchestration | `application/services/adr_review_service.py:55-120` | `review_adr`, TaskGroup, `validate_review_result` (advisory) |
| Merge | `domain/adr/review_llm_schema.py:98-135` | `merge_review_results` — always 5 `SectionName` ratings |
| Runtime validator | `application/review_quality.py:25-34` | `validate_review_result` |
| Projection success | `infrastructure/adapters/persistence/projections/adr_projection.py:79-96` | `apply_review_result` → `after_review`, clears `review_error` |
| Projection failure | `adr_projection.py:98-118` | `record_review_failure` → `review_failed` + `review_error` JSON |
| Retry command | `application/commands/retry_adr_for_review.py:41-86` | `mark_in_review` clears `review_error`; new `ADRSubmittedForReview` |
| Fake LLM | `infrastructure/llm/fake_completion.py:23-66` | `FakeLlmCompletionPort` |
| DI | `infrastructure/llm/factory.py:14-50` | `build_adr_review_service` |

### Risk #1 — review contract at API boundary

**Static-only path (default tests):** Starter ADR template leaves all five sections as gaps → `present_sections` empty → no LLM calls → merge yields five score-0 ratings. Passes `validate_review_result`. `test_get_adr_includes_section_ratings_after_review` asserts count and bounds but not actionable scores.

**LLM merge path (untested at API):** `review_quality/fixtures/complete.md` forces six LLM calls (5 sections + cross-section). `FakeLlmCompletionPort` returns valid `SectionReviewPayload` with scores 1–5. Through API, this should produce five ratings with non-zero scores on all sections and valid annotation kinds.

**Advisory validation gap:**

```113:120:backend/application/services/adr_review_service.py
        validation = validate_review_result(markdown, result)
        if not validation.passed:
            _logger.warning(
                "adr_review.validation_failed",
                failures=validation.failures,
            )

        return result
```

Handler test `test_run_ai_review.py:236-268` confirms invalid merged result → `AIReviewCompleted`, not failure.

**API serialization:** `_to_adr_response` (`adr.py:301-310`) omits `section_ratings` when tuple is empty (JSON `null`).

**Injection patterns for API tests:**

```python
monkeypatch.setattr(
    "infrastructure.bootstrap.build_adr_review_service",
    lambda _settings: AdrReviewService(custom_port),
)
```

Wire-level malformed payloads raise before merge → `RetryableInternalError` → `review_failed`. Service returning empty ratings bypasses merge → currently `after_review` (gap).

### Risk #2 — failure and recovery

**Failure persistence:** `_fail_review` appends `AIReviewFailed` with `source_event_id=stored_event.id`, calls `record_review_failure` with `ReviewErrorMetadata` (`run_ai_review.py:171-226`).

**Aggregate:** `fail_review` requires `in_review` → `review_failed`, clears `review_result`, sets `review_error` (`aggregate.py:195-247`).

**Retry:** `retry_review` requires `review_failed` → `in_review`, clears error fields (`aggregate.py:174-179`). Projection `mark_in_review` clears `review_error` column (`adr_projection.py:36-47`).

**Stuck `in_review` scenarios:** Transient between submit and handler finish; poison-pill if `_fail_review` itself fails (event stays unprocessed). Not covered by API tests.

**Existing API coverage:**

| Test | Lines | Gap |
|------|-------|-----|
| `test_retry_review_from_review_failed_returns_202` | 796-851 | Stops at `in_review`; no post-retry drain |
| `test_invalid_review_surfaces_review_error` | 543-602 | Documents wrong success on empty ratings |

### Risk #5 — idempotency

**Handler skip** (`run_ai_review.py:95-115`): skips when `AIReviewFailed` already exists for same `source_event_id` (`duplicate_failure`) or aggregate `after_review` (`already_reviewed`).

**Retry HTTP:** Not idempotent — second call while `in_review` → `400`. Advisory lock `lock_aggregate` serializes concurrent retries.

**Success replay:** `test_replay_does_not_duplicate_completed_review` (`699-749`) — success path only.

**Gaps:** double-retry, concurrent retry, failure replay, event-count assertions, retry-then-fail-again.

### Existing test assets

| Asset | Location | Reuse |
|-------|----------|-------|
| API helpers | `test_adr_api.py:416-445` | `_drain_event_bus`, `_wait_for_review_status`, `_stop_event_worker` |
| Failing service pattern | `test_adr_api.py:812-820` | `FailingReviewService` raising `RetryableInternalError` |
| Invalid service pattern | `test_adr_api.py:558-574` | Returns empty ratings — update assertions |
| Handler unit tests | `test_run_ai_review.py` | Failure, skip, duplicate_failure |
| Review fixtures | `tests/review_quality/fixtures/complete.md` | Force LLM path |
| Event SQL pattern | `test_auth.py:306` | `SELECT event_type FROM events` |

## Code References

- `backend/application/handlers/run_ai_review.py:24-85` — exception → `_fail_review`
- `backend/application/handlers/run_ai_review.py:95-115` — `_skip_reason` duplicate failure
- `backend/application/services/adr_review_service.py:74-95` — TaskGroup failure propagation
- `backend/application/review_quality.py:25-34` — advisory validator
- `backend/domain/adr/review_llm_schema.py:98-135` — merge always five sections
- `backend/infrastructure/api/routers/adr.py:301-310` — empty ratings → null JSON
- `backend/tests/infrastructure/api/test_adr_api.py:543-602` — empty ratings gap test
- `backend/tests/infrastructure/api/test_adr_api.py:796-851` — partial retry recovery test
- `backend/tests/review_quality/cases.py:64-68` — `complete` case fixture

## Architecture Insights

- Submit/retry return 202 immediately; projection goes `in_review` before worker runs. Tests must drain event bus (or `_wait_for_review_status`) for async completion.
- `TaskGroupEventBus` is a polling worker, not `asyncio.TaskGroup`. LLM parallelism uses TaskGroup inside `AdrReviewService`.
- Test oracle for Risk #1 should come from test-plan contract (five sections, score bounds, annotation kinds) and fixture markdown — not `FakeLlmCompletionPort` feedback strings.
- Minimal production change likely needed for Risk #1: enforce `validate_review_result` in handler (fail → `review_failed`) to match test-plan "cannot silently complete as empty."

## Historical Context

- Phase 1 (`context/changes/testing-critical-path-api-integration/`) established two-user IDOR and persistence patterns in same test file.
- `test_invalid_review_surfaces_review_error` name implies error surfacing but asserts `after_review` — rename/update when contract is tightened.

## Related Research

- `context/changes/testing-critical-path-api-integration/research.md` — API test patterns, auth_client fixture
- `backend/tests/review_quality/test_runtime_validation.py` — service-level contract over all fixtures

## Open Questions

1. **Product decision (Risk #1):** Block invalid merged results at handler (`review_failed`) vs. accept empty ratings with documented test? Test plan intent favors blocking.
2. **Event-stream assertions:** Include SQL `events` table checks in API tests or rely on projection + handler unit tests?
3. **Concurrent retry test:** Worth threading complexity in CI or advisory-lock + double-sequential retry sufficient for Risk #5?
