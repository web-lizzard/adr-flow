# Quality Gates Wiring Implementation Plan

## Overview

Phase 4 of the test rollout: wire CI and local commands so the test floor built in Phases 1–3 is enforced on every PR. Risks #1–#5 are already covered by pytest, Vitest, and Playwright specs — this change makes those suites block merge instead of relying on local `just test` + `pnpm run e2e`.

## Current State Analysis

Phases 1–3 shipped the risk-protecting tests. Local commands run the full suites (`just test-backend` → full pytest; `just test-frontend` → Vitest; `pnpm run e2e` → Playwright with dual webServer). CI enforcement is partial:

- `backend-ci.yml` runs only `tests/infrastructure/adapters/persistence` + `tests/domain` — missing `tests/infrastructure/api/`, `tests/application/`, `tests/review_quality/` where Risks #1–#5 live.
- No frontend CI workflow for Vitest.
- No E2E CI workflow despite Playwright config being CI-ready (`forbidOnly`, retries, `reuseExistingServer: !process.env.CI`).
- Pre-commit covers lint/type only (correct per `test-plan.md` §5); no `just e2e` recipe.
- Stale docs: `AGENTS.md` claims CI is not in-repo; `test-plan.md` §4 says E2E runner is "none yet"; `README.md` understates pre-commit hooks.

### Key Discoveries:

- Backend CI already provisions Postgres 15 and runs migrations — expanding to full pytest is low incremental cost (`.github/workflows/backend-ci.yml:25-62`).
- Playwright `webServer` starts backend with `LLM_PROVIDER=fake` and frontend with `NUXT_API_UPSTREAM` — E2E CI must provide `DATABASE_URL`, `JWT_SECRET`, and `CORS_ORIGINS` including `http://127.0.0.1:3100` via job env (`frontend/playwright.config.ts:32-47`, `backend/infrastructure/config.py:23-27`).
- Path filters on `backend-ci.yml` (`backend/**` only) let frontend-only PRs skip all backend tests — a blind spot for cross-stack regressions (`backend-ci.yml:8-9`).
- Full suites are the selection mechanism — no pytest markers or Vitest tags per risk; run complete trees (`research.md` Architecture Insight #6).
- Pre-commit test hooks are expensive; `test-plan.md` §5 marks them "recommended" not "required" — keep lint/type in pre-commit, defer optional test hook.

## Desired End State

Every PR to `main` runs three CI workflows with no path filters:

1. **Backend CI** — full `uv run pytest` + migrations + ruff + ty (protects Risks #1–#5 at API/handler layer).
2. **Frontend CI** — Vitest + ESLint + `tsc` (protects Risk #4 frontend persistence tests and UI regressions).
3. **E2E CI** — Postgres + migrations + Playwright chromium + `pnpm run e2e` (protects north-star + auth flows).

Local ergonomics: `just e2e` wraps `pnpm run e2e`; `just test` unchanged. Documentation reflects actual gate state. `test-plan.md` §6 Phase 4 cookbook populated.

Verification: open a PR and confirm all three workflows run and pass on green `main`. A deliberate test failure in `test_adr_api.py` blocks backend CI merge.

## What We're NOT Doing

- **Pre-commit test hook** — defer; full suite on every commit is too slow for MVP. Cursor `test-after-edit.sh` remains the agent-loop feedback path.
- **Coverage thresholds** — explicitly defer; no pytest-cov or vitest coverage gates until hot-path gaps justify maintenance cost.
- **Deploy pipeline test steps** — `deploy-gcp.yml` stays deploy-only; tests gate at PR time.
- **New test authoring** — suites from Phases 1–3 are complete; this is wiring only.
- **Unified single `test.yml`** — separate workflows per stack match existing `backend-ci.yml` pattern and keep job logs scoped.
- **httpx AsyncClient migration** — out of scope (deferred from Phases 1–2).
- **Review-failed E2E or registration UI E2E** — already deferred in Phase 3.

## Implementation Approach

Four sequential phases: expand the existing backend gate first (smallest diff, immediate Risk #1–#5 API coverage), add frontend unit CI, add E2E CI (heaviest job — Postgres + dual servers + browser install), then local/docs cleanup. Each phase is independently verifiable via workflow file inspection and local command parity.

## Critical Implementation Details

**E2E CI env** — Playwright's backend `webServer` inherits the job's environment. The E2E job must set `JWT_SECRET` (≥32 chars), `DATABASE_URL`, and `CORS_ORIGINS` including `http://127.0.0.1:3100` before `pnpm run e2e`. Migrations must run against that database before Playwright starts servers — the webServer does not migrate.

**Path filters removed** — All three test workflows trigger on every `pull_request` to `main` with no `paths:` filter. This closes the frontend-only PR blind spot at the cost of ~3–5 min CI per PR regardless of changed files.

## Phase 1: Expand Backend CI

### Overview

Replace the pytest subset in `backend-ci.yml` with the full backend test tree so API integration and handler tests for Risks #1–#5 run on every PR.

### Changes Required:

#### 1. Full pytest in backend CI

**File**: `.github/workflows/backend-ci.yml`

**Intent**: Run the complete backend test suite that Phases 1–2 built, not just persistence and domain subsets. This is the primary gate for Risks #1–#5 at the API and handler layers.

**Contract**:
- Replace `uv run pytest tests/infrastructure/adapters/persistence tests/domain` with `uv run pytest` (full tree per `backend/pyproject.toml` `testpaths = ["tests"]`).
- Rename the step from "Run persistence and domain tests" to "Run tests".
- Remove the `paths:` filter under `on.pull_request` so the workflow runs on every PR to `main`, not only `backend/**` changes. Keep the workflow self-trigger on edits to `backend-ci.yml` implicitly via no filter.

#### 2. Concurrency group naming

**File**: `.github/workflows/backend-ci.yml`

**Intent**: Keep cancel-in-progress behavior meaningful after removing path filters.

**Contract**: No change required to concurrency group — `backend-ci-${{ github.event.pull_request.number }}` remains valid.

### Success Criteria:

#### Automated Verification:

- Workflow YAML is valid: inspect `.github/workflows/backend-ci.yml` for correct pytest command and absent `paths:` key
- Local parity: `cd backend && uv run pytest` passes (full suite green before merge)
- Lint unchanged: `cd backend && uv run ruff check .` passes
- Types unchanged: `cd backend && uv run ty check` passes

#### Manual Verification:

- Push a branch and confirm Backend CI runs on a PR that touches only `frontend/**` (proves path filter removal)
- Confirm CI log shows API tests (`test_adr_api.py`) executing, not only persistence/domain

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Add Frontend CI

### Overview

Create a GitHub Actions workflow that runs Vitest, ESLint, and TypeScript checking on every PR — enforcing Risk #4 frontend persistence tests and component regressions at merge time.

### Changes Required:

#### 1. Frontend CI workflow

**File**: `.github/workflows/frontend-ci.yml` (new)

**Intent**: Mirror the backend CI pattern for the Nuxt frontend: install deps, run unit tests, lint, and typecheck on every PR to `main`.

**Contract**:
- Trigger: `pull_request` → `main`, no `paths:` filter.
- Concurrency: `frontend-ci-${{ github.event.pull_request.number }}`, `cancel-in-progress: true`.
- Permissions: `contents: read`.
- Steps: checkout → setup Node (22, matching devcontainer) → setup pnpm (read version from `packageManager` field in `frontend/package.json` or use `pnpm/action-setup` with version from lockfile) → `pnpm install --frozen-lockfile` in `frontend/` → `pnpm run test` → `pnpm run lint` → `pnpm run typecheck`.
- No Postgres required — Vitest uses jsdom.

### Success Criteria:

#### Automated Verification:

- Local parity: `cd frontend && pnpm run test` passes
- Local parity: `cd frontend && pnpm run lint` passes
- Local parity: `cd frontend && pnpm run typecheck` passes
- Workflow file exists at `.github/workflows/frontend-ci.yml`

#### Manual Verification:

- Push a branch and confirm Frontend CI runs and passes on a PR
- Confirm Vitest output includes persistence-related tests (`useAdrPersistence.test.ts` or similar)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Add E2E CI

### Overview

Create a GitHub Actions workflow that provisions Postgres, runs migrations, installs Playwright browsers, and executes the full E2E suite — enforcing the north-star review and auth flows on every PR.

### Changes Required:

#### 1. E2E CI workflow

**File**: `.github/workflows/e2e-ci.yml` (new)

**Intent**: Run `pnpm run e2e` in CI with the same deterministic setup as local dev: fake LLM, fresh servers, single worker.

**Contract**:
- Trigger: `pull_request` → `main`, no `paths:` filter.
- Concurrency: `e2e-ci-${{ github.event.pull_request.number }}`, `cancel-in-progress: true`.
- Job env:
  - `CI: true` (enables Playwright `forbidOnly`, retries, fresh servers)
  - `DATABASE_URL` / `TEST_DATABASE_URL`: same Postgres connection string as backend-ci (`postgresql://ci:ci@localhost:5432/adrflow_test`)
  - `JWT_SECRET`: a CI-only secret string ≥32 characters
  - `CORS_ORIGINS`: `http://127.0.0.1:3100` (matches Playwright frontend URL)
- Services: Postgres 15 alpine with same healthcheck pattern as `backend-ci.yml`.
- Steps (order matters):
  1. Checkout
  2. Setup uv → `uv sync --frozen` in `backend/`
  3. `uv run alembic upgrade head` in `backend/`
  4. Setup Node + pnpm in `frontend/`
  5. `pnpm install --frozen-lockfile` in `frontend/`
  6. Install Playwright browser: `pnpm exec playwright install --with-deps chromium` in `frontend/` (or equivalent one-liner that installs chromium with system deps)
  7. `pnpm run e2e` in `frontend/` (Playwright webServer starts backend + frontend; inherits job env)

#### 2. Playwright install script (optional convenience)

**File**: `frontend/package.json`

**Intent**: Provide a CI-friendly script alias for browser installation if `playwright install --with-deps chromium` is not already covered by existing scripts.

**Contract**: Only add a `e2e:install` script (e.g. `"e2e:install": "playwright install --with-deps chromium"`) if the E2E workflow benefits from a named script. Skip if `pnpm exec playwright install --with-deps chromium` is sufficient inline in the workflow.

### Success Criteria:

#### Automated Verification:

- Local parity (without CI env): `cd frontend && pnpm run e2e` passes
- Workflow file exists at `.github/workflows/e2e-ci.yml`
- E2E specs present: `frontend/e2e/auth-login.spec.ts`, `frontend/e2e/north-star-review.spec.ts`

#### Manual Verification:

- Push a branch and confirm E2E CI runs on a PR (expect ~2–5 min job duration)
- Confirm CI log shows both `auth-login` and `north-star-review` specs passing
- Confirm Playwright starts backend on port 8100 and frontend on 3100 without env-related startup failures

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Local Ergonomics & Documentation

### Overview

Add `just e2e`, fix stale documentation, and populate the test-plan Phase 4 cookbook so contributors and agents know the enforced gate state.

### Changes Required:

#### 1. Justfile e2e recipe

**File**: `Justfile`

**Intent**: Provide a root-level command for E2E parity with `just test-frontend` / `just test-backend`.

**Contract**: Add `e2e` recipe: `cd frontend && pnpm run e2e`. Place near existing `test-*` recipes.

#### 2. AGENTS.md CI and test documentation

**File**: `AGENTS.md`

**Intent**: Replace stale "CI workflows are not in-repo yet" with accurate gate documentation. Agents should know what runs on PR vs locally.

**Contract**:
- Update the CI/workflows bullet to describe the three PR workflows: `backend-ci.yml` (full pytest), `frontend-ci.yml` (Vitest + lint + typecheck), `e2e-ci.yml` (Playwright).
- Document `just e2e` alongside `just test` / `just test-*`.
- Keep pre-commit description accurate (lint/type only, no test hook).
- Keep Cursor hook guidance unchanged (related tests on edit, not full suite).

#### 3. Test plan stack and cookbook updates

**File**: `context/foundation/test-plan.md`

**Intent**: Reflect shipped Playwright runner and document Phase 4 quality gate wiring in the cookbook.

**Contract**:
- §4 E2E: replace "Runner: none yet" with Playwright (`frontend/playwright.config.ts`, `pnpm run e2e` / `just e2e`).
- Update the E2E row in the stack table with actual version from `frontend/package.json`.
- §3 Phase 4 status: mark complete after implementation (or note "in progress" during rollout — final state is `complete`).
- §6 Phase 4 cookbook: document CI workflows, local commands (`just test`, `just e2e`), pre-commit scope (lint/type), and explicit deferral of coverage thresholds and pre-commit test hooks.

#### 4. README pre-commit description

**File**: `README.md`

**Intent**: Fix outdated claim that pre-commit config "starts with trailing-whitespace only."

**Contract**: Update the post-create / pre-commit paragraph to list actual hooks: trailing-whitespace, Ruff, Prettier, ESLint, `tsc`, ty — and note that tests run in CI, not pre-commit.

#### 5. Change status

**File**: `context/changes/testing-quality-gates-wiring/change.md`

**Intent**: Mark the change as planned and record update date.

**Contract**: Set `status: planned`, `updated: 2026-07-13`.

### Success Criteria:

#### Automated Verification:

- `just e2e` runs Playwright (command exists and invokes `pnpm run e2e`)
- `just test` still runs frontend + backend unit suites
- `pre-commit run --all-files` passes (doc-only changes should not break hooks)

#### Manual Verification:

- `AGENTS.md` accurately describes CI workflows and local test commands
- `test-plan.md` §4 and §6 Phase 4 reflect current state
- `README.md` pre-commit description matches `.pre-commit-config.yaml`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to archive.

---

## Testing Strategy

### Unit Tests:

- No new tests — existing pytest and Vitest suites are the gates under test.
- Phase 1 verification: confirm `test_adr_api.py` and `test_run_ai_review.py` appear in backend CI logs.

### Integration Tests:

- Backend CI runs the full integration tree including fake-LLM injection tests from Phase 2.
- E2E CI runs the two Playwright specs from Phase 3.

### Manual Testing Steps:

1. Open a PR from a branch that touches only docs — confirm all three CI workflows trigger.
2. Temporarily break an assertion in `test_patch_returns_404_for_other_users_adr` — confirm backend CI fails.
3. Revert break — confirm all workflows green.
4. Run `just e2e` locally — confirm parity with CI E2E job.

## Performance Considerations

- Removing path filters means every PR runs backend + frontend + E2E jobs (~3–5 min total wall time with parallel jobs). Acceptable for MVP team size; revisit path filters if CI queue becomes a bottleneck.
- E2E uses `workers: 1` and `retries: 2` in CI — intentional for stability.
- Pre-commit stays fast (lint/type only) to preserve developer flow.

## Migration Notes

No data migration. Existing contributors need no action beyond pulling the branch — CI enforcement is automatic on next PR. Local workflow: run `just test` and `just e2e` before pushing (recommended, not hooked).

## References

- Related research: `context/changes/testing-quality-gates-wiring/research.md`
- Test plan gates: `context/foundation/test-plan.md` §5
- Backend CI baseline: `.github/workflows/backend-ci.yml`
- Playwright CI config: `frontend/playwright.config.ts`
- Phase 3 E2E plan: `context/changes/testing-e2e-auth-north-star-review/plan.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Expand Backend CI

#### Automated

- [x] 1.1 Workflow YAML is valid: inspect `.github/workflows/backend-ci.yml` for correct pytest command and absent `paths:` key
- [x] 1.2 Local parity: `cd backend && uv run pytest` passes (full suite green before merge)
- [x] 1.3 Lint unchanged: `cd backend && uv run ruff check .` passes
- [x] 1.4 Types unchanged: `cd backend && uv run ty check` passes

#### Manual

- [ ] 1.5 Push a branch and confirm Backend CI runs on a PR that touches only `frontend/**` (proves path filter removal)
- [ ] 1.6 Confirm CI log shows API tests (`test_adr_api.py`) executing, not only persistence/domain

### Phase 2: Add Frontend CI

#### Automated

- [ ] 2.1 Local parity: `cd frontend && pnpm run test` passes
- [ ] 2.2 Local parity: `cd frontend && pnpm run lint` passes
- [ ] 2.3 Local parity: `cd frontend && pnpm run typecheck` passes
- [ ] 2.4 Workflow file exists at `.github/workflows/frontend-ci.yml`

#### Manual

- [ ] 2.5 Push a branch and confirm Frontend CI runs and passes on a PR
- [ ] 2.6 Confirm Vitest output includes persistence-related tests (`useAdrPersistence.test.ts` or similar)

### Phase 3: Add E2E CI

#### Automated

- [ ] 3.1 Local parity (without CI env): `cd frontend && pnpm run e2e` passes
- [ ] 3.2 Workflow file exists at `.github/workflows/e2e-ci.yml`
- [ ] 3.3 E2E specs present: `frontend/e2e/auth-login.spec.ts`, `frontend/e2e/north-star-review.spec.ts`

#### Manual

- [ ] 3.4 Push a branch and confirm E2E CI runs on a PR (expect ~2–5 min job duration)
- [ ] 3.5 Confirm CI log shows both `auth-login` and `north-star-review` specs passing
- [ ] 3.6 Confirm Playwright starts backend on port 8100 and frontend on 3100 without env-related startup failures

### Phase 4: Local Ergonomics & Documentation

#### Automated

- [ ] 4.1 `just e2e` runs Playwright (command exists and invokes `pnpm run e2e`)
- [ ] 4.2 `just test` still runs frontend + backend unit suites
- [ ] 4.3 `pre-commit run --all-files` passes (doc-only changes should not break hooks)

#### Manual

- [ ] 4.4 `AGENTS.md` accurately describes CI workflows and local test commands
- [ ] 4.5 `test-plan.md` §4 and §6 Phase 4 reflect current state
- [ ] 4.6 `README.md` pre-commit description matches `.pre-commit-config.yaml`
