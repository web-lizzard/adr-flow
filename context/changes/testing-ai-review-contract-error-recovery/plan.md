# Plan: AI review contract and error recovery tests

## Goal

Close Phase 2 rollout gaps from `context/foundation/test-plan.md`: prove merged review contract at the API boundary (Risk #1), handler failure → `review_failed` → retry recovery (Risk #2), and retry/idempotency guards (Risk #5) by extending `backend/tests/infrastructure/api/test_adr_api.py` and enforcing validation at the handler when merged output is invalid.

## Progress

- [x] 1.1 Enforce `validate_review_result` failure → `review_failed` in `RunAiReviewHandler` — 84eaac8
- [x] 1.2 Update `test_invalid_review_surfaces_review_error` to assert `review_failed` (rename if needed) — 84eaac8
- [x] 2.1 Add API contract test: `complete.md` ADR → five section ratings via real merge path
- [x] 2.2 Add API test: wire-level LLM failure → `review_failed` with `review_error`
- [ ] 3.1 Add dedicated submit-failure API test with `review_error` field assertions
- [ ] 3.2 Extend retry test: drain after retry → `after_review`; assert `review_error` cleared
- [ ] 4.1 Add double-retry test: second `POST /retry-review` while `in_review` → `400`
- [ ] 4.2 Add failure replay idempotency test (reset `processed_at`, re-drain → single `AIReviewFailed`)
- [ ] 5.1 Update `context/foundation/test-plan.md` §6 Phase 2 cookbook patterns
- [ ] 5.2 Run targeted pytest and pre-commit on touched files

## Out of scope

- Real LLM provider calls or probabilistic quality eval
- Frontend review UI tests (Phase 3)
- Changing 404-only IDOR policy (Phase 1)
- Poison-pill tests where `_fail_review` itself raises
- Concurrent retry with threads (advisory lock + sequential double-retry suffices for Risk #5)
- httpx `AsyncClient` migration

## Current state

Research confirms advisory validation is the root cause of Risk #1 silent empty completion. Failure and skip logic exist in handler; API tests stop short of full recovery and idempotency proofs.

| Gap | Existing pattern | File:line |
|-----|------------------|-----------|
| Empty ratings reach `after_review` | `InvalidReviewService` monkeypatch | `test_adr_api.py:543-602` |
| LLM merge at API | None | Use `complete.md` + default `auth_client` (fake LLM) |
| Fail → retry → complete | Partial (stops at `in_review`) | `test_adr_api.py:796-851` |
| Double retry | None | Mirror `test_domain_error_handler_returns_kind` |
| Failure replay | Success replay only | `test_adr_api.py:699-749` |

## Key decisions

| Decision | Choice | Rationale | Source |
|----------|--------|-----------|--------|
| Invalid merged output | Handler calls `validate_review_result`; on failure → `_fail_review` with `internal_error` | Matches test-plan "cannot silently complete as empty"; smallest fix at persistence boundary | Research + test plan Risk #1 |
| Contract oracle | Five sections, score 0–5, feedback when score ≥ 1, annotation `kind` in allowed set | Independent of LLM wording | Test plan Risk #1 anti-pattern |
| Complete ADR fixture | `review_quality/fixtures/complete.md` via PATCH/create content | Forces all LLM calls through real `AdrReviewService` | Research |
| Wire failure injection | Custom `LlmCompletionPort` raising `LlmParseError` or invalid structured response | Proves transport/parse → `review_failed` without bypassing merge | Research |
| Retry recovery proof | Drain after retry with succeeding `FakeLlmCompletionPort` | Closes fail → retry → `after_review` chain | Test plan Risk #2 |
| Idempotency scope | Sequential double-retry + failure replay | Cheaper than threaded concurrency; advisory lock covered by domain/command unit tests | Test plan Risk #5 |
| Event assertions | Count `AIReviewFailed` / `ADRSubmittedForReview` via SQL in replay test | Proves stream integrity beyond projection | Research gap |

---

## Phase 1: Enforce review validation at handler (Risk #1)

### Overview

Make invalid merged `ReviewResult` transition to `review_failed` instead of `after_review`. Update the existing API regression test that documents the gap.

### Changes Required

#### 1. `backend/application/handlers/run_ai_review.py`

**Intent:** After `review_adr` returns, call `validate_review_result(markdown, result)`. If `not validation.passed`, call `_fail_review` with `kind="internal_error"` and a message summarizing failure count (not full failure list — avoid oracle coupling).

**Contract:**
- Valid merged result → existing `_complete_review` path unchanged
- Invalid merged result → `AIReviewFailed` + `record_review_failure`; projection `review_failed`
- Skip rules (`_skip_reason`) unchanged

#### 2. `backend/tests/application/handlers/test_run_ai_review.py`

**Intent:** Update `test_completes_review_with_invalid_result` (or equivalent) to expect `AIReviewFailed` instead of `AIReviewCompleted`.

#### 3. `backend/tests/infrastructure/api/test_adr_api.py`

**Intent:** Rename/update `test_invalid_review_surfaces_review_error`:
- Assert `review_status` → `review_failed`
- Assert `review_error` present with `kind` and `message`
- Assert `section_ratings` absent or null on GET
- Remove assertion that status is `after_review`

### Success Criteria

- `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py tests/infrastructure/api/test_adr_api.py -k "invalid_review" -v` passes

---

## Phase 2: Merged review contract at API (Risk #1)

### Overview

Prove that a complete ADR reviewed through the real service at the HTTP boundary returns five valid section ratings. Prove wire-level LLM failure surfaces `review_failed`.

### Changes Required

#### 1. `backend/tests/infrastructure/api/test_adr_api.py`

**Helper:** `_create_adr_with_content(client, markdown: str) -> UUID` — create ADR then PATCH or POST save with fixture content.

**Contract per test:**

1. **`test_complete_adr_review_returns_five_section_ratings_at_api`**
   - Load `complete.md` from `tests/review_quality/fixtures/`
   - Create ADR with that content
   - `POST submit-review` → drain/wait → `after_review`
   - `GET /api/adrs/{id}`:
     - `section_ratings` length == 5
     - Sections == `{Context, Options, Decision, Status, Consequences}`
     - Each `score` in 0..5; if `score >= 1`, `feedback` non-empty
     - Each annotation `kind` in `ReviewAnnotationKind` values (if annotations present)
   - Do **not** assert exact feedback strings from fake LLM

2. **`test_malformed_llm_response_surfaces_review_failed`**
   - Monkeypatch `build_adr_review_service` → `AdrReviewService(MalformedPort())`
   - `MalformedPort.complete_structured` raises `LlmParseError` (or returns payload failing Pydantic)
   - Submit complete ADR → drain
   - Assert `review_failed`, `review_error.kind` in (`retryable_internal_error`, `internal_error`)

### Success Criteria

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "complete_adr_review or malformed_llm" -v` passes

---

## Phase 3: Failure and full retry recovery (Risk #2)

### Overview

Dedicated failure test and extended retry test proving end-to-end recovery to `after_review`.

### Changes Required

#### 1. `backend/tests/infrastructure/api/test_adr_api.py`

1. **`test_review_failure_persists_review_error`**
   - `FailingReviewService` (existing pattern) on submit
   - Drain → assert `review_failed`
   - Assert `review_error`: `kind`, `message`, `source_event_id` (non-null UUID string), `failed_at` present
   - `GET /review-status` matches

2. **`test_retry_from_review_failed_completes_review`**
   - Extend `test_retry_review_from_review_failed_returns_202` or replace with fuller test:
   - Phase A: fail on first submit (`FailingReviewService`)
   - Phase B: swap to default/`FakeLlmCompletionPort` service, `POST retry-review`
   - Drain/wait → `after_review`
   - Assert `review_error` is null; `section_ratings` length == 5

Use separate `TestClient` app instances or reset monkeypatch between phases if needed.

### Success Criteria

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "review_failure or retry_from_review_failed" -v` passes

---

## Phase 4: Retry idempotency (Risk #5)

### Overview

Prove double-retry is rejected and failure replay does not duplicate failure events.

### Changes Required

#### 1. `backend/tests/infrastructure/api/test_adr_api.py`

1. **`test_double_retry_while_in_review_returns_400`**
   - Fail → `review_failed` → successful retry → `in_review` (do not drain to completion)
   - Second `POST /retry-review` → `400`, `kind == adr_invalid_retry_status`
   - Query `events`: exactly one `ADRSubmittedForReview` after the failure event (initial submit + one retry)

2. **`test_failure_replay_does_not_duplicate_review_failed`**
   - Mirror `test_replay_does_not_duplicate_completed_review` pattern for failure path:
   - Submit with `FailingReviewService` → drain → `review_failed`
   - `UPDATE events SET processed_at = NULL WHERE event_type = 'ADRSubmittedForReview' ...` (latest submit)
   - Re-drain
   - Assert still one `AIReviewFailed` for that submit's `source_event_id`; status remains `review_failed`

### Success Criteria

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "double_retry or failure_replay" -v` passes

---

## Phase 5: Cookbook + verification

### Overview

Document shipped patterns in test-plan §6 and verify module health.

### Changes Required

#### 1. `context/foundation/test-plan.md` §6 Phase 2

Replace TBD with subsections:
- **Review contract at API** — `complete.md` fixture, five ratings oracle, malformed LLM → `review_failed`; anti-pattern: wire-model-only or exact LLM wording
- **Failure → retry recovery** — failing service, `review_error` fields, full drain to `after_review`; anti-pattern: happy-path-only
- **Retry idempotency** — double-retry 400, failure replay; anti-pattern: asserting 202 only

#### 2. Full verification

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py tests/application/handlers/test_run_ai_review.py -v`
- `pre-commit run --files` on touched backend files + test-plan

### Success Criteria

- Full targeted modules green; pre-commit clean

---

## Testing Strategy

| Test | Risk | Behavior asserted | Anti-pattern avoided |
|------|------|-------------------|----------------------|
| Handler validation enforcement | #1 | Invalid merge → `review_failed` | Assuming validator blocks at service |
| Complete ADR API contract | #1 | Five ratings, structural validity | Default template static-only path |
| Malformed LLM API | #1 | Parse failure → `review_failed` | Service bypass |
| Failure persists error | #2 | `review_error` metadata on API | TaskGroup "must catch" assumption |
| Full retry recovery | #2 | `after_review` after retry | Stopping at `in_review` |
| Double retry | #5 | Second retry 400 | 202-only idempotency claim |
| Failure replay | #5 | Single `AIReviewFailed` | Projection-only checks |

## References

- Research: `context/changes/testing-ai-review-contract-error-recovery/research.md`
- Test plan: `context/foundation/test-plan.md` §2 Risks #1–#2–#5, §3 Phase 2
- Baseline patterns: `backend/tests/infrastructure/api/test_adr_api.py:416-445`, `:796-851`
- Fixtures: `backend/tests/review_quality/fixtures/complete.md`
