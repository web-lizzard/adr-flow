# Quality Gates Wiring — Plan Brief

> Full plan: `context/changes/testing-quality-gates-wiring/plan.md`
> Research: `context/changes/testing-quality-gates-wiring/research.md`

## What & Why

Phases 1–3 built tests protecting risks #1–#5 (review contract, failure recovery, IDOR, persistence, retry idempotency). Phase 4 wires CI and local commands so those tests block merge instead of relying on developers running `just test` locally. The test floor exists — enforcement does not.

## Starting Point

- `backend-ci.yml` runs only persistence + domain pytest subsets; API/handler tests are skipped.
- No frontend CI, no E2E CI.
- Pre-commit is lint/type only (correct).
- `just test` works locally; no `just e2e`. Playwright is CI-ready but unwired.
- Docs are stale (`AGENTS.md` says no CI; `test-plan.md` §4 says no E2E runner).

## Desired End State

Every PR to `main` runs three parallel CI workflows (no path filters): full backend pytest, frontend Vitest + lint + typecheck, and Playwright E2E with Postgres. `just e2e` exists. Documentation matches reality. A PR that breaks any risk-protecting test cannot merge.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| CI workflow shape | Separate `backend-ci`, `frontend-ci`, `e2e-ci` | Matches existing pattern; scoped job logs per stack | Plan |
| Path filters | None — all test jobs on every PR | Closes frontend-only PR blind spot | Plan |
| E2E frequency | Every PR | `test-plan.md` §5 requires e2e on PR after Phase 3 | Research |
| Pre-commit tests | Defer — lint/type only | Full suite too slow; test-plan marks test hook "recommended" not "required" | Research |
| Coverage thresholds | Explicitly defer | No tooling configured; maintenance cost not justified yet | Research |
| `just e2e` | Add to Justfile | Parity with `just test-*` for local ergonomics | Plan |
| Doc updates | Include in Phase 4 | Fix stale AGENTS.md, test-plan, README | Research |

## Scope

**In scope:**
- Expand `backend-ci.yml` to full pytest, remove path filters
- New `frontend-ci.yml` (Vitest + lint + typecheck)
- New `e2e-ci.yml` (Postgres + migrations + Playwright + `pnpm run e2e`)
- `just e2e` recipe
- Update `AGENTS.md`, `test-plan.md` §4/§6, `README.md`

**Out of scope:**
- Pre-commit test hook
- Coverage thresholds
- Deploy pipeline test steps
- New test authoring
- Unified single `test.yml`

## Architecture / Approach

Three independent GitHub Actions workflows trigger on every PR to `main`. Backend and E2E jobs share the Postgres 15 service container pattern from existing `backend-ci.yml`. E2E job sets `CI=1`, `JWT_SECRET`, `CORS_ORIGINS`, runs migrations, then `pnpm run e2e` — Playwright's `webServer` config starts backend (`LLM_PROVIDER=fake`) and Nuxt dev server. Frontend CI needs no database.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Expand backend CI | Full pytest on every PR | Longer backend job if suite grows |
| 2. Add frontend CI | Vitest + lint + type on every PR | pnpm/Node setup first-time wiring |
| 3. Add E2E CI | Playwright north-star + auth on every PR | Env vars / migration ordering; ~2–5 min job |
| 4. Local + docs | `just e2e`, fix stale docs, test-plan cookbook | Doc drift if not updated atomically |

**Prerequisites:** Phases 1–3 test suites green locally (`just test`, `pnpm run e2e`).
**Estimated effort:** ~1–2 sessions across 4 phases.

## Open Risks & Assumptions

- E2E CI flakiness from poll/event-bus timing — mitigated by existing 15s timeouts and `retries: 2`.
- All PRs pay full CI cost (~3–5 min) with no path filters — acceptable for MVP; revisit if queue grows.
- `deploy-gcp.yml` deploys without test steps — assumes PR gates are sufficient.

## Success Criteria (Summary)

- All three CI workflows run and pass on every PR to `main`.
- Breaking a risk-protecting test (e.g. IDOR assertion) blocks backend CI.
- `just e2e` and documentation accurately describe the enforced gate state.
