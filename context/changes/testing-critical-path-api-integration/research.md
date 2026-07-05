---
date: 2026-07-05T17:12:55+00:00
researcher: Composer
git_commit: f61d702888e98075fc7cd76b290f7e9295e30019
branch: main
repository: adr-flow
topic: "Rollout Phase 1 — Critical-path API integration (IDOR + persistence)"
tags: [research, testing, api, idor, persistence, adr]
status: complete
last_updated: 2026-07-05
last_updated_by: Composer
---

# Research: Rollout Phase 1 — Critical-path API integration

**Date**: 2026-07-05T17:12:55+00:00
**Researcher**: Composer
**Git Commit**: f61d702888e98075fc7cd76b290f7e9295e30019
**Branch**: main
**Repository**: adr-flow

## Research Question

Ground rollout Phase 1 of `context/foundation/test-plan.md`.

**Risks to verify:** #3 (IDOR — User A cannot read/modify User B's ADR), #4 backend path (persistence API round-trips).

**Risk response guidance to verify, not blindly accept:**
- **Risk #3:** prove User A's token cannot fetch, patch, save, delete, review, or retry User B's ADR; challenge "authenticated = authorized" on mutating routes; avoid testing only unauthenticated 401 or read-path IDOR.
- **Risk #4 (backend):** prove content persists via API after save; challenge "save endpoint works so draft loss is impossible"; avoid testing API save without verifying persistence round-trip at integration layer.

**Hot-spot directories (likelihood evidence — NOT anchors):** `backend/domain/user/`, `frontend/app/composables/`.

**Stack:** pytest 9.x + FastAPI TestClient today; test plan specifies httpx AsyncClient for Phase 1.

## Summary

Authorization is **correct by design** but **incompletely proven at the HTTP layer**. Every ADR route requires a Bearer JWT; ownership is enforced in command/query handlers (repository `find_by_id_for_owner` on reads; aggregate `user_id` comparison on writes). Cross-user access consistently returns **404** (`AdrNotFound`) — not 403 (`AdrAccessDenied` exists but is never raised).

Read-path IDOR and most mutating routes already have cross-user denial tests in `backend/tests/infrastructure/api/test_adr_api.py`. **Three mutating gaps remain:** `PATCH`, `POST /save`, and `POST /retry-review`.

For Risk #4, PATCH persistence is partially covered (`test_get_after_patch_returns_updated_content`). **Beacon save (`POST /save`) asserts 204 only** — no GET round-trip proves content survived. Both save routes delegate to the same `UpdateAdrContentCommandHandler`, so one integration test pattern covers both paths.

**Cheapest useful layer:** extend existing `test_adr_api.py` with sync `TestClient` (already wired to real Postgres). Migrating to httpx AsyncClient is optional style alignment, not required for signal.

**Response guidance verified:** no speculative risks; hot-spot evidence aligns with actual enforcement points in application handlers.

## Detailed Findings

### ADR API surface

All routes mount at `/api/adrs` via `backend/infrastructure/bootstrap.py` and `backend/infrastructure/api/routers/adr.py`.

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| `POST` | `/api/adrs` | `create_adr` | `get_current_user_id` |
| `GET` | `/api/adrs` | `list_adrs` | same |
| `GET` | `/api/adrs/search` | `search_adrs` | same |
| `GET` | `/api/adrs/{adr_id}` | `get_adr` | same |
| `PATCH` | `/api/adrs/{adr_id}` | `update_adr` | same |
| `POST` | `/api/adrs/{adr_id}/save` | `beacon_save_adr` | same |
| `POST` | `/api/adrs/{adr_id}/submit-review` | `submit_adr_for_review` | same |
| `POST` | `/api/adrs/{adr_id}/retry-review` | `retry_adr_for_review` | same |
| `POST` | `/api/adrs/{adr_id}/publish` | `publish_adr` | same |
| `DELETE` | `/api/adrs/{adr_id}` | `delete_adr` | same |
| `GET` | `/api/adrs/{adr_id}/review-status` | `get_adr_review_status` | same |

`POST /api/adrs` is not an IDOR vector — server generates `adr_id` and binds to authenticated user in `CreateAdrCommandHandler`.

### Ownership enforcement (Risk #3)

**Authentication layer** (`backend/infrastructure/api/dependencies.py:95-114`): missing or invalid Bearer token → 401.

**Authorization layer — reads:** `SqlAdrRepository.find_by_id_for_owner` filters `(adr_id, user_id, is_deleted=False)`. Query handlers raise `AdrNotFound` when no row matches.

**Authorization layer — writes:** command handlers load event stream, rehydrate aggregate, compare `adr.user_id.value != command.user_id` → `AdrNotFound`. Applies to:
- `UpdateAdrContentCommandHandler` (PATCH + beacon save)
- `SubmitAdrForReviewCommandHandler`
- `RetryAdrForReviewCommandHandler`
- `PublishAdrCommandHandler`
- `SoftDeleteAdrCommandHandler`

**403 vs 404 policy** (`backend/infrastructure/api/exception_handlers.py:19-21`):
- `AdrNotFound` → 404 (used for missing ADR **and** owner mismatch — intentional non-leakage)
- `AdrAccessDenied` → 403 (defined in `backend/domain/errors.py` but **never raised**)

List/search isolate by filtering — intruder gets 200 + empty results, not 404.

### Existing test coverage matrix (API integration)

File: `backend/tests/infrastructure/api/test_adr_api.py`

| Route | Cross-user denial | Persistence round-trip |
|-------|-------------------|------------------------|
| `GET /{id}` | ✅ `:214-225` → 404 | — |
| `GET /` (list) | ✅ `:292-303` → empty | — |
| `GET /search` | ✅ `:188-199` → empty | — |
| `GET /{id}/review-status` | ✅ `:426-436` → 404 | — |
| `PATCH /{id}` | ❌ **GAP** | ✅ `:150-162` (GET after PATCH) |
| `POST /{id}/save` | ❌ **GAP** | ❌ **GAP** (204 only at `:137-147`) |
| `POST /{id}/submit-review` | ✅ `:439-449` → 404 | — |
| `POST /{id}/retry-review` | ❌ **GAP** | — |
| `POST /{id}/publish` | ✅ `:802-812` → 404 | — |
| `DELETE /{id}` | ✅ `:869-879` → 404 | — |

**Two-user fixture pattern** already established at `:214-225`:
1. Owner registers, creates ADR, captures `adr_id`
2. Clear auth, intruder registers
3. Intruder calls route → assert 404
4. (Recommended for mutating tests) switch back to owner, GET → assert unchanged

### Persistence data flow (Risk #4)

Both `PATCH` and `POST /save` call `_handle_update` → `UpdateAdrContentCommandHandler`:

```
PATCH /save → UpdateAdrContentCommand
  → load event stream, rehydrate aggregate, owner check
  → aggregate.update_content / update_title
  → append ADRContentUpdated (sync projection event)
  → adr_projection.update_content (same transaction)
  → commit

GET /api/adrs/{id} → GetAdrQueryHandler → find_by_id_for_owner → projection row
```

Key files:
- Router: `backend/infrastructure/api/routers/adr.py:204-268`
- Command: `backend/application/commands/update_adr_content.py:25-79`
- Event: `backend/domain/adr/events.py:18-21` (`ADRContentUpdated`)
- Projection: `backend/infrastructure/adapters/persistence/projections/adr_projection.py:25-34`
- Read: `backend/infrastructure/adapters/persistence/repositories/adr_repository.py:19-33`

Domain guard: edits blocked when `status == in_review` → `AdrEditWhileInReview` (400), tested at `test_adr_api.py:228-240`.

### Test infrastructure available

| Fixture | Location | Purpose |
|---------|----------|---------|
| `auth_client` | `backend/tests/infrastructure/api/conftest.py:14-72` | Real Postgres + `create_app`, sync TestClient |
| `clean_auth_tables` | same (autouse) | Truncates `adrs`, `users`, `events` between tests |
| `register_and_get_token`, `set_bearer_auth` | same | Two-user auth switching |
| `_register_user`, `_create_adr` | `test_adr_api.py:19-28` | Local helpers (inline, not exported) |

`httpx` is a dependency (`backend/pyproject.toml`) but **no AsyncClient usage exists** in tests today. Existing `TestClient` + real Postgres already provides integration-layer signal.

### Response guidance verification

| Risk | Guidance claim | Verified? | Correction |
|------|----------------|-----------|------------|
| #3 | Must test mutating routes, not only GET | ✅ Confirmed — PATCH, save, retry lack cross-user tests | None |
| #3 | Challenge "authenticated = authorized" | ✅ Handlers enforce ownership; gap is test proof, not code | None |
| #3 | Avoid read-path IDOR only | ✅ Read paths covered; mutating gaps are the work | None |
| #4 | Must verify persistence round-trip | ✅ PATCH has GET follow-up; beacon save does not | Beacon save is primary gap |
| #4 | Challenge "save endpoint works" | ✅ Same handler for both routes; beacon path untested end-to-end | None |
| #4 | httpx AsyncClient | ⚠️ Style preference | TestClient is sufficient; httpx migration optional |

**No speculative risks.** `AdrAccessDenied` (403) is dead code — document 404-only policy; do not add 403 tests unless product changes policy.

## Code References

- `backend/infrastructure/api/routers/adr.py:204-268` — PATCH and beacon save handlers
- `backend/infrastructure/api/dependencies.py:95-114` — JWT auth dependency
- `backend/application/commands/update_adr_content.py:36-42` — owner check on write
- `backend/infrastructure/adapters/persistence/repositories/adr_repository.py:19-33` — owner-scoped read
- `backend/infrastructure/api/exception_handlers.py:19-21` — 404/403 mapping
- `backend/tests/infrastructure/api/test_adr_api.py:137-147` — beacon save (no GET follow-up)
- `backend/tests/infrastructure/api/test_adr_api.py:150-162` — PATCH persistence round-trip
- `backend/tests/infrastructure/api/test_adr_api.py:214-225` — two-user GET IDOR pattern
- `backend/tests/application/commands/test_update_adr_content.py:112-132` — unit-level owner mismatch

## Architecture Insights

- **Hexagonal + CQRS-lite:** writes go through command handlers → events → sync projection; reads hit projection only. Persistence tests at API layer validate the full write→read contract without mocking repositories.
- **404-for-both-missing-and-forbidden:** consistent anti-enumeration policy; tests should assert `status_code == 404`, optionally `kind == "adr_not_found"`.
- **Beacon save is not a separate persistence path** — identical command handler as PATCH; one round-trip test pattern serves both Risk #3 (cross-user denial) and Risk #4 (persistence proof).

## Historical Context

- `context/foundation/test-plan.md` §3 Phase 1 — defines risks #3 and #4 (backend path) as scope; notes existing read-path IDOR coverage.
- `context/changes/test-plan-refresh-2026-07-05/research.md` — refresh identified mutating IDOR gaps and beacon save round-trip as Phase 1 priorities.
- `backend/tests/infrastructure/api/test_adr_api.py` — pre-rollout baseline already has substantial API coverage; Phase 1 extends rather than bootstraps.

## Recommended Phase 1 test additions

### Risk #3 — mutating IDOR (must-add)

| Test | Route | Assert |
|------|-------|--------|
| `test_patch_returns_404_for_other_users_adr` | `PATCH /{owner_adr_id}` | 404; owner GET unchanged |
| `test_beacon_save_returns_404_for_other_users_adr` | `POST /{owner_adr_id}/save` | 404; owner GET content unchanged |
| `test_retry_review_returns_404_for_other_users_adr` | `POST /{owner_adr_id}/retry-review` | 404; seed owner ADR in `review_failed` first |

For retry: reuse failing-LLM bootstrap pattern from `test_adr_api.py:705-760` to put owner's ADR in `review_failed`, then intruder attempts retry.

### Risk #4 — persistence round-trip (must-add)

| Test | Route | Assert |
|------|-------|--------|
| `test_get_after_beacon_save_returns_updated_content` | `POST /save` then `GET` | content matches saved payload |

Optional stronger assertions (lower priority):
- Title-only beacon save preserves content
- `updated_at` increases after save
- Direct DB row check (pattern from delete test at `:834-838`)

### Anti-patterns to avoid (from test plan)

- Testing only unauthenticated 401 without cross-user denial
- Asserting PATCH response body without separate GET (already fixed for PATCH; apply same to beacon)
- Oracle copied from handler implementation — assert user-visible persisted content via GET
- Migrating to httpx before closing coverage gaps (signal first, style second)

## Open Questions

1. **httpx migration scope:** adopt AsyncClient in Phase 1 plan, or keep TestClient and defer httpx to a later hygiene pass? Research recommends signal-first with existing fixtures.
2. **Retry cross-user seed complexity:** failing-LLM integration test is heavy; acceptable for Phase 1 or seed `review_failed` via lower-level fixture? Plan should pick cheapest path that still hits HTTP layer.
3. **Defense-in-depth on existing tests:** should publish/delete cross-user tests also verify owner ADR unchanged? Nice-to-have, not blocking.

## Related Research

- `context/changes/test-plan-refresh-2026-07-05/research.md` — test base profile and refreshed risk map
- `context/foundation/test-plan.md` §2 Risk Response Guidance — source intent for this phase
