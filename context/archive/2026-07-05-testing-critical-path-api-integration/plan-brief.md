# Critical-path API integration tests — Plan Brief

> Full plan: `context/changes/testing-critical-path-api-integration/plan.md`
> Research: `context/changes/testing-critical-path-api-integration/research.md`

## What & Why

Add four pytest API integration tests to close rollout Phase 1 gaps: prove User B cannot mutate User A's ADR (PATCH, beacon save, retry-review) and prove beacon save persists content via a GET round-trip. Authorization logic already exists in command handlers; this phase adds the HTTP-level proof the test plan requires.

## Starting Point

`test_adr_api.py` already covers read-path IDOR, submit/publish/delete cross-user denial, and PATCH persistence via GET. Three mutating routes and beacon save round-trip lack coverage. Tests use sync `TestClient` against real Postgres via `auth_client` fixture.

## Desired End State

Phase 1 rollout status can advance to implement/complete with:
- Cross-user 404 on PATCH, POST /save, POST /retry-review plus owner state unchanged
- POST /save followed by GET proving persisted content
- §6 cookbook documenting mutating IDOR and persistence round-trip patterns

## Key Decisions Made

| Decision | Choice | Why | Source |
|----------|--------|-----|--------|
| Test transport | Keep `TestClient` | Existing fixtures; httpx adds no signal | Research |
| Retry test seed | Owner draft ADR | Owner check precedes status validation | Research + code |
| Test count | 4 new tests in one file | Cheapest layer; no new infrastructure | Plan |
| Cookbook | Update §6 in final sub-phase | Patterns ship with tests | Test plan |

## Scope

**In scope:** 3 IDOR tests, 1 persistence test, §6 cookbook update, pytest + pre-commit verification

**Out of scope:** httpx migration, frontend persistence (Phase 3), 401 gap-fill, dead 403 code cleanup

## Phases at a glance

1. **Mutating IDOR** — PATCH, save, retry cross-user tests
2. **Persistence** — beacon save GET round-trip
3. **Cookbook + verify** — document patterns, run full module + pre-commit
