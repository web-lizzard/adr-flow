# Plan: Critical-path API integration tests

## Goal

Close Phase 1 rollout gaps from `context/foundation/test-plan.md`: prove mutating IDOR protection (Risk #3) and backend persistence round-trips (Risk #4) at the HTTP integration layer by extending `backend/tests/infrastructure/api/test_adr_api.py`.

## Progress

- [x] 1.1 Add cross-user denial test for `PATCH /api/adrs/{id}` — ade4b8d
- [x] 1.2 Add cross-user denial test for `POST /api/adrs/{id}/save` — ade4b8d
- [x] 1.3 Add cross-user denial test for `POST /api/adrs/{id}/retry-review` — ade4b8d
- [x] 2.1 Add beacon save persistence round-trip (`POST /save` → `GET`) — c3c7c0b
- [x] 3.1 Update `context/foundation/test-plan.md` §6 Phase 1 cookbook patterns
- [x] 3.2 Run targeted pytest and pre-commit on touched files

## Out of scope

- httpx `AsyncClient` migration (TestClient + real Postgres already provides integration signal; defer style alignment)
- Unauthenticated 401 tests for routes that already lack them (PATCH, save, search, review-status)
- Defense-in-depth assertions on existing publish/delete cross-user tests (owner GET unchanged)
- Frontend blur/unload persistence (Risk #4 frontend path — Phase 3)
- Removing dead `AdrAccessDenied` (403) code — document 404-only policy only

## Current state

Research (`research.md`) confirms authorization is correct in handlers; gaps are **missing HTTP-level proof**:

| Gap | File | Existing pattern to copy |
|-----|------|--------------------------|
| PATCH cross-user | `test_adr_api.py` | `test_accessing_another_users_adr_returns_404` (`:214-225`) |
| Beacon save cross-user | same | same two-user fixture |
| Retry cross-user | same | same; owner check runs before status — draft ADR suffices |
| Beacon save round-trip | same | `test_get_after_patch_returns_updated_content` (`:150-162`) |

## Key decisions

| Decision | Choice | Rationale | Source |
|----------|--------|-----------|--------|
| Test client | Keep sync `TestClient` | Existing `auth_client` fixture; signal before style | Research |
| Retry cross-user seed | Owner draft ADR only | `RetryAdrForReviewCommandHandler` checks owner before `retry_review()` | Research + code |
| Cross-user assertion | 404 + owner GET unchanged | Proves no mutation leaked; matches 404-only policy | Test plan |
| Persistence oracle | Separate GET after save | Independent of PATCH/save response body | Test plan Risk #4 |
| Cookbook update | Final sub-phase | Ship patterns when tests land | Test plan §6 |

---

## Phase 1: Mutating IDOR integration tests (Risk #3)

### Overview

Add three API integration tests proving User B cannot mutate User A's ADR on PATCH, beacon save, and retry-review routes.

### Changes Required

#### 1. `backend/tests/infrastructure/api/test_adr_api.py`

**Intent:** Extend the established two-user fixture pattern with mutating-route coverage and owner-state verification.

**Contract per test:**

1. **`test_patch_returns_404_for_other_users_adr`**
   - Setup: owner creates ADR with known `content`; capture `adr_id`
   - Act: intruder `PATCH` with `{"content": "stolen", "title": "Hijacked"}`
   - Assert: `status_code == 404`
   - Assert: owner `GET` → original `content` and `title` unchanged

2. **`test_beacon_save_returns_404_for_other_users_adr`**
   - Setup: owner creates ADR; owner saves initial content via PATCH or POST save
   - Act: intruder `POST /{id}/save` with `{"content": "intruder content"}`
   - Assert: `status_code == 404`
   - Assert: owner `GET` → content unchanged

3. **`test_retry_review_returns_404_for_other_users_adr`**
   - Setup: owner creates draft ADR (no review_failed seeding required)
   - Act: intruder `POST /{id}/retry-review`
   - Assert: `status_code == 404`
   - Assert: owner `GET` → `status` still `draft` (no spurious state change)

**Helper reuse:** `register_and_get_token`, `set_bearer_auth`, `clear_bearer_auth` from `conftest.py`; mirror structure of `test_accessing_another_users_adr_returns_404`.

### Success Criteria

#### Automated Verification

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "other_users_adr" -v` passes
- `cd backend && uv run ruff check tests/infrastructure/api/test_adr_api.py` passes

---

## Phase 2: Beacon save persistence round-trip (Risk #4)

### Overview

Prove `POST /api/adrs/{id}/save` persists content readable via a subsequent `GET` — closing the backend persistence gap independent of PATCH response body.

### Changes Required

#### 1. `backend/tests/infrastructure/api/test_adr_api.py`

**Intent:** Add GET follow-up to beacon save path; oracle is persisted content from independent read.

**Contract:**

- **`test_get_after_beacon_save_returns_updated_content`**
  - Create ADR as authenticated user
  - `POST /{id}/save` with `{"content": "Beacon persisted content"}`
  - Assert: `status_code == 204`
  - `GET /{id}` → `content == "Beacon persisted content"`

Optional (only if trivial): assert `title` unchanged when saving content-only payload.

### Success Criteria

#### Automated Verification

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -k "beacon_save" -v` passes (existing + new test)

---

## Phase 3: Cookbook + verification

### Overview

Document shipped patterns in test-plan §6 and verify the full API test module still passes.

### Changes Required

#### 1. `context/foundation/test-plan.md` §6 Phase 1

**Intent:** Replace TBD with concrete cookbook entries naming behavior, test file, and anti-patterns avoided.

**Contract:** Two subsections:

- **Mutating IDOR denial** — two-user fixture; routes PATCH, POST /save, POST /retry-review; assert 404 + owner state unchanged; anti-pattern: read-path-only IDOR
- **Persistence API round-trip** — POST /save then GET; anti-pattern: asserting 204/200 without separate read

#### 2. Full verification

- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -v`
- `pre-commit run --files backend/tests/infrastructure/api/test_adr_api.py context/foundation/test-plan.md`

### Success Criteria

#### Automated Verification

- Full `test_adr_api.py` module green
- Pre-commit clean on touched files

---

## Testing Strategy

### Integration tests (this change)

| Test | Behavior asserted | Regression caught | Anti-pattern avoided |
|------|-------------------|-------------------|----------------------|
| PATCH cross-user | Intruder cannot change title/content | Missing ownership check on PATCH | Read-only IDOR coverage |
| Beacon save cross-user | Intruder cannot overwrite content | Missing ownership on unload path | Testing 204 only |
| Retry cross-user | Intruder cannot trigger retry | Authz hole on recovery route | Assuming retry validates status before owner |
| GET after beacon save | Saved content survives read | Projection/write failure on beacon path | Oracle from save response only |

### Edge cases explicitly deferred

- Title-only beacon save round-trip
- `kind == "adr_not_found"` body assertion on cross-user tests
- DB-level row assertion after save (delete test pattern exists; not required for Risk #4)

## References

- Research: `context/changes/testing-critical-path-api-integration/research.md`
- Test plan: `context/foundation/test-plan.md` §2 Risks #3–#4, §3 Phase 1
- Baseline patterns: `backend/tests/infrastructure/api/test_adr_api.py:137-162`, `:214-225`
