---
date: 2026-07-13T00:21:00+02:00
researcher: Composer
git_commit: 00b71e65463288d4fa33069b07a124960450b3d9
branch: main
repository: adr-flow
topic: "Quality gates wiring — CI, pre-commit, and test command coverage for risks 1–5"
tags: [research, quality-gates, ci, pre-commit, pytest, vitest, playwright, testing]
status: complete
last_updated: 2026-07-13
last_updated_by: Composer
---

# Research: Quality gates wiring (Phase 4 test rollout)

**Date**: 2026-07-13
**Researcher**: Composer
**Git Commit**: `00b71e65463288d4fa33069b07a124960450b3d9`
**Branch**: main
**Repository**: adr-flow

## Research Question

How should Phase 4 wire quality gates so CI and hooks enforce the test floor built in Phases 1–3 — specifically ensuring risks #1–#5 cannot regress undetected on merge?

## Summary

Phases 1–3 shipped the tests; Phase 4 wiring is largely **missing**. The repo has a **partial** `backend-ci.yml` that runs only persistence + domain pytest subsets on backend-only PRs. There is **no frontend CI**, **no E2E CI**, and **no test hooks in pre-commit**. Local commands (`just test`, `pnpm run e2e`) run the full suites but are not enforced at commit or PR time.

**Key gaps vs `context/foundation/test-plan.md` §5:**

| Gate | Required after | Current state |
|------|----------------|---------------|
| Backend unit + integration (full pytest) | Phase 2 | CI runs subset only (`persistence` + `domain`) |
| Frontend Vitest | Phase 2 | No CI workflow |
| E2E north-star + auth | Phase 3 | `pnpm run e2e` exists locally; no CI job |
| Pre-commit test hook | Phase 4 (recommended) | Not configured |
| Coverage thresholds | Phase 4 (optional) | Not configured |

**Risk enforcement today:** All risk-protecting tests exist and pass via `just test` + `pnpm run e2e` locally, but **most are not in any CI path**. A PR that breaks review contract, IDOR, persistence, or retry idempotency can merge if it only touches `frontend/**` (no CI trigger) or if it touches `backend/**` but the failing tests live outside the CI subset (`tests/infrastructure/api/`, `tests/application/`, `tests/review_quality/`).

## Detailed Findings

### CI workflows (`.github/workflows/`)

#### `backend-ci.yml` — partial backend gate

Triggers on `pull_request` to `main` with path filter `backend/**` and the workflow file itself (`backend-ci.yml:5-10`). Uses ephemeral Postgres 15 (`backend-ci.yml:25-38`).

Steps after checkout:
- Migrations: `alembic upgrade head`, `current --check-heads`, `alembic check` (`backend-ci.yml:48-58`)
- **Tests (subset only):** `uv run pytest tests/infrastructure/adapters/persistence tests/domain` (`backend-ci.yml:60-62`)
- Lint: `ruff check` (`backend-ci.yml:64-66`)
- Types: `ty check` (`backend-ci.yml:68-70`)

**Not run in CI:** `tests/infrastructure/api/` (Risks #1–#5 API tests), `tests/application/` (handler failure/retry), `tests/review_quality/`, `tests/test_health.py`.

#### `deploy-gcp.yml` — deploy only

Push-to-main deploy pipeline. No test steps.

#### Missing workflows

- No `frontend-ci.yml` (or equivalent) for Vitest on `frontend/**` PRs
- No E2E job for Playwright on PR
- No workflow that runs `just test` parity

### Pre-commit (`.pre-commit-config.yaml`)

Hooks cover lint and typecheck only:
- `trailing-whitespace` (repo-wide)
- `ruff` + `ruff-format` (`^backend/`)
- `frontend-prettier`, `frontend-eslint`, `frontend-typecheck` (`^frontend/`)
- `backend-ty` (`^backend/`)

**No pytest, vitest, or playwright hooks.** `AGENTS.md:9` correctly documents pre-commit as lint/format/type only.

### Justfile and package scripts

`Justfile:17-25` defines:
- `just test-frontend` → `pnpm run test` (Vitest)
- `just test-backend` → `uv run pytest` (full backend tree per `backend/pyproject.toml:36-38`)
- `just test` → both sequentially

**Gap:** No `just e2e` wrapping `cd frontend && pnpm run e2e`.

`frontend/package.json:15-20`:
- `test` → `vitest run`
- `e2e` → `playwright test`
- `e2e:auth` → setup project only

### Playwright E2E (Phase 3 shipped)

`frontend/playwright.config.ts`:
- `testDir: "e2e"` (`:8`)
- CI mode: `forbidOnly`, `retries: 2`, `workers: 1` (`:10-12`)
- Projects: `setup` → `chromium` with `storageState` (`:18-30`)
- `webServer` spins backend (`LLM_PROVIDER=fake`, port 8100) + Nuxt dev (port 3100) (`:32-47`)
- `reuseExistingServer: !process.env.CI` — fresh servers in CI

Specs: `frontend/e2e/auth-login.spec.ts`, `frontend/e2e/north-star-review.spec.ts`, `frontend/e2e/auth.setup.ts`.

Vitest (`frontend/vitest.config.ts`) covers `tests/**/*.test.ts` only — E2E is Playwright-only.

### Cursor agent hooks (not git gates)

`.cursor/hooks.json` runs `lint-after-edit.sh` and `test-after-edit.sh` on `afterFileEdit`.

`test-after-edit.sh`:
- Frontend: `vitest related <file> --run --passWithNoTests`
- Backend: mapped pytest targets via `resolve_pytest_targets`
- Exits 0 even on failure (does not block agent flow)
- Does not run E2E

These provide edit-time feedback for agents, not commit/PR enforcement.

### Risk-to-test map (what CI must eventually run)

No pytest markers or Vitest tags scope risk tests — full suites are the selection mechanism.

#### Risk #1 — Review contract

| Test | Location |
|------|----------|
| `test_complete_adr_review_returns_five_section_ratings_at_api` | `backend/tests/infrastructure/api/test_adr_api.py:510` |
| `test_malformed_llm_response_surfaces_review_failed` | `backend/tests/infrastructure/api/test_adr_api.py:547` |
| `test_invalid_review_surfaces_review_error` | `backend/tests/infrastructure/api/test_adr_api.py:667` |
| `test_run_ai_review_fails_when_merged_result_fails_validation` | `backend/tests/application/handlers/test_run_ai_review.py:236` |
| E2E happy path | `frontend/e2e/north-star-review.spec.ts:11` |

#### Risk #2 — Failure → review_failed → retry

| Test | Location |
|------|----------|
| `test_review_failure_persists_review_error` | `backend/tests/infrastructure/api/test_adr_api.py:982` |
| `test_retry_from_review_failed_completes_review` | `backend/tests/infrastructure/api/test_adr_api.py:1040` |
| Handler failure paths | `backend/tests/application/handlers/test_run_ai_review.py:148,199` |

#### Risk #3 — Mutating IDOR denial

| Test | Location |
|------|----------|
| `test_patch_returns_404_for_other_users_adr` | `backend/tests/infrastructure/api/test_adr_api.py:260` |
| `test_beacon_save_returns_404_for_other_users_adr` | `backend/tests/infrastructure/api/test_adr_api.py:289` |
| `test_retry_review_returns_404_for_other_users_adr` | `backend/tests/infrastructure/api/test_adr_api.py:317` |
| Plus read/submit/publish/delete cross-user tests | `test_adr_api.py:220,246,398,641,654,1337,1404` |

#### Risk #4 — Persistence

| Test | Location |
|------|----------|
| `test_get_after_beacon_save_returns_updated_content` | `backend/tests/infrastructure/api/test_adr_api.py:165` |
| `test_get_after_patch_returns_updated_content` | `backend/tests/infrastructure/api/test_adr_api.py:182` |
| Blur/unload Vitest tests | `frontend/tests/useAdrPersistence.test.ts`, `adr.store.test.ts`, `adr-editor-page.test.ts`, `adr-markdown-editor.test.ts` |
| E2E partial (title blur) | `frontend/e2e/north-star-review.spec.ts:11` |

#### Risk #5 — Retry idempotency

| Test | Location |
|------|----------|
| `test_double_retry_while_in_review_returns_400` | `backend/tests/infrastructure/api/test_adr_api.py:1116` |
| `test_failure_replay_does_not_duplicate_review_failed` | `backend/tests/infrastructure/api/test_adr_api.py:1201` |
| Handler idempotency | `backend/tests/application/handlers/test_run_ai_review.py:275,308` |

### Command coverage matrix

| Bucket | `just test-backend` | `just test` | `pnpm run e2e` | Current CI |
|--------|---------------------|-------------|----------------|------------|
| Backend API risk tests | Yes | Yes | No | **No** |
| Handler tests | Yes | Yes | No | **No** |
| Frontend Vitest | No | Yes | No | **No** |
| Playwright E2E | No | No | Yes | **No** |
| Persistence/domain subset | Yes | Yes | No | **Yes** (only this) |

### Stale documentation

- `AGENTS.md:47` — "CI workflows are not in-repo yet" contradicts `backend-ci.yml`
- `test-plan.md` §4 L105-106 — still says "E2E runner: none yet" (Phase 3 shipped Playwright)
- `test-plan.md` §6 Phase 4 — still TBD
- `README.md` — pre-commit description may be outdated (lint hooks added)

## Code References

- `.github/workflows/backend-ci.yml:60-62` — CI pytest subset (persistence + domain only)
- `.pre-commit-config.yaml:1-49` — lint/type hooks, no tests
- `Justfile:17-25` — `just test` / `test-frontend` / `test-backend`
- `frontend/package.json:15-20` — `test`, `e2e`, `e2e:auth` scripts
- `frontend/playwright.config.ts:1-48` — E2E runner with CI-aware webServer
- `frontend/vitest.config.ts` — unit test include pattern
- `.cursor/hooks/test-after-edit.sh` — agent related-test hook
- `backend/pyproject.toml:36-38` — pytest `testpaths = ["tests"]`
- `backend/tests/infrastructure/api/test_adr_api.py` — primary API integration gate for Risks #1–#5
- `backend/tests/application/handlers/test_run_ai_review.py` — handler-layer risk tests
- `frontend/tests/useAdrPersistence.test.ts` — unload/beacon persistence (Risk #4)

## Architecture Insights

1. **Phase ordering was intentional:** test-plan §3 rationale says Phase 4 last because wiring CI before tests exist would block merges on incomplete coverage. Tests now exist; wiring is the remaining work.

2. **Backend CI already has Postgres:** expanding to full `uv run pytest` is low incremental cost — the service container and migration steps are in place.

3. **E2E CI needs Postgres + dual webServer:** Playwright config already starts backend and frontend with `LLM_PROVIDER=fake`. CI job must set `CI=1`, install Playwright browsers, provide `DATABASE_URL`/`TEST_DATABASE_URL`, and run migrations before E2E.

4. **Path-filter blind spot:** backend-ci only triggers on `backend/**` changes. Frontend-only PRs skip all backend tests even if they break API assumptions. A frontend-ci workflow (or a unified test workflow) closes this gap.

5. **Pre-commit test hooks are expensive:** full `just test` + E2E on every commit is slow. test-plan §5 marks pre-commit tests as "recommended" not "required". Plan should choose between: (a) full suite in pre-commit, (b) fast subset locally + full suite in CI only, or (c) optional pre-commit test hook behind an env flag.

6. **Coverage thresholds optional:** no pytest-cov or vitest coverage scripts configured. Defer unless hot-path gaps justify the maintenance cost.

## Historical Context (from prior changes)

- **Phase 1** (`testing-critical-path-api-integration/plan.md`) — verification via targeted pytest + `pre-commit run --files`; no CI wiring
- **Phase 2** (`testing-ai-review-contract-error-recovery/plan.md`) — same local gates; sequential retry tests chosen over threaded concurrency for CI simplicity
- **Phase 3** (`testing-e2e-auth-north-star-review/plan.md`) — `pnpm run e2e` as primary verification; 15s UI timeouts for CI variance; review-failed E2E deferred to Phase 2 API tests
- **Tech stack** (`context/foundation/tech-stack.md:33-36`) — `ci_provider: github-actions`, `ci_default_flow: auto-deploy-on-merge`
- **Test plan** (`context/foundation/test-plan.md:78,123-132`) — Phase 4 goal and quality gates table

## Related Research

- `context/changes/testing-critical-path-api-integration/research.md` — IDOR and persistence test patterns
- `context/changes/testing-ai-review-contract-error-recovery/research.md` — review contract and retry harness
- `context/changes/testing-e2e-auth-north-star-review/research.md` — Playwright setup, CI determinism, DB isolation open question

## Open Questions

1. **Pre-commit scope:** Run full `just test` on commit, a faster subset, or defer tests to CI only with pre-commit staying lint/type?
2. **CI workflow shape:** Separate `frontend-ci.yml` + expand `backend-ci.yml` vs single `test.yml` running all gates on every PR?
3. **E2E on every PR vs main-only:** test-plan §5 says "CI on PR" for e2e — confirm budget for ~2-3 min Playwright job with Postgres + dual servers.
4. **Path filters:** Should backend tests run when only `frontend/**` changes (and vice versa) to catch cross-stack regressions?
5. **Coverage thresholds:** Add now or explicitly defer?
6. **Doc updates:** Fix `AGENTS.md`, `test-plan.md` §4/§6, and `README.md` as part of Phase 4 implementation?
