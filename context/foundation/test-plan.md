---
project: adr-flow
version: 1
status: active
created: 2026-06-16
updated: 2026-06-16
prd_version: 1
test_base_profile: sparse (effectively none — existing tests generated without a plan; treat as bare)
---

# Test Plan: adr-flow

> Phased test rollout for ADR Flow. Each rollout phase opens its own change folder
> and runs through the `/research` → `/plan` → `/implement` chain.
> Re-run `/test-plan` to check status or advance to the next phase.

## §1 Strategy

### Principles

1. **Cost × signal.** Every test this rollout adds — classic or AI-native — must answer one question: *what is the cheapest test that gives a real signal for this risk?* Do not promote to e2e because it "feels safer"; do not layer a vision model on top of a deterministic diff that already catches the regression.

2. **User concerns are evidence.** Risks the team has lived through (or fears living through) carry the same weight as PRD lines or hot-spot data.

3. **Risks are scenarios, not code locations.** Every risk in §2 describes a *failure the user would notice*, cited with evidence (PRD lines, interview answers, hot-spot directories). No risk row cites a file path, function name, or schema name as its anchor. Code-level grounding is `/research`'s job, produced per rollout phase against the current codebase.

### Negative space — what we do NOT test

- shadcn-vue UI components (library code, not application logic)
- Alembic migration files (run once, verified manually)
- ORM model definitions (tested implicitly through integration; no standalone model tests)
- LLM client library wrappers (test the contract we enforce, not the HTTP client)
- Snapshot tests (break on every style tweak, catch nothing for this product)
- Full probabilistic AI review evaluation with F-scores (deferred post-MVP; see §2 Risk #1 response guidance)

## §2 Risk Map

### Top Risks

| # | Risk (failure scenario) | Impact | Likelihood | Source(s) |
|---|---|---|---|---|
| 1 | AI review returns false-positive annotations or rejects a valid ADR — user publishes a well-formed ADR and review flags non-existent issues, eroding trust in the product wedge | High | High | PRD NFR: >=80% section-gap detection accuracy; PRD NFR: annotation actionability; Interview Q1; Roadmap S-04 + F-01 |
| 2 | ADR status transition accepts an illegal move (e.g. `draft`→`proposed` skipping review, or editing while `in_review`) — the 4-status contract breaks silently | High | Medium | PRD FR-007 (4-status lifecycle); PRD FR-005 (no edit in `in_review`); PRD FR-008/FR-009; Roadmap S-04/S-05 |
| 3 | User A can read or modify User B's ADR via direct API call — IDOR; per-user isolation fails | High | Medium | PRD NFR: per-user data isolation; PRD Access Control; Interview Q1 ("auth tests not too tight") |
| 4 | Draft content lost on browser refresh, tab close, or session expiry — save-on-blur or save-on-unload silently fails | High | Medium | PRD NFR: no draft loss; PRD FR-006; PRD Open Question #1; Roadmap S-02 unknown |
| 5 | Event store append succeeds but projection update fails — read model is stale; user sees outdated ADR status or missing ADR | Medium | Medium | Architecture: synchronous projection in command path; Infrastructure risk register; Hot-spot dir `backend/infrastructure/adapters/persistence/` (8 touches/30d) |
| 6 | Async event handler (AI review) crashes and leaves ADR stuck in `in_review` — user waits indefinitely; no recovery path | High | Medium | Architecture: asyncio.TaskGroup dispatch; Infrastructure risk register; Interview Q3 ("async event worker... crucial part of the MVP"); Roadmap S-04 |
| 7 | Auth token forgery or session bypass — JWT validation is weak, allowing unauthenticated or cross-user access | High | Low | PRD Access Control; Tech-stack: custom JWT; Interview Q1 ("auth tests not too tight"); AGENTS.md: "Auth belongs in the backend" |

### Risk Response Guidance

| Risk # | What would prove protection | Must challenge | Context needed | Likely cheapest layer | Anti-pattern to avoid |
|---|---|---|---|---|---|
| 1 | Given fixture ADRs with known section presence, the review pipeline returns correctly structured annotations that flag the right sections; annotation schema is always valid JSON conforming to F-01's contract | "The LLM is smart enough" — must verify *our* parsing, schema validation, and section-detection logic, not the LLM's prose quality | F-01 quality-check harness; annotation response schema; prompt template; what counts as "missing" vs "empty" | Integration test with fixture ADRs against the deterministic layer (schema + section detection); defer probabilistic eval post-MVP | Building a full evaluation dataset as MVP gate; asserting exact LLM wording instead of structural properties; the oracle problem (expected value copied from the implementation) |
| 2 | Attempting `draft`→`proposed` (skipping review) raises an error; editing content while status is `in_review` raises an error; `after_review`→`proposed` succeeds without re-triggering review | "Happy-path transitions work, so the lifecycle is correct" — must test *illegal* transitions, not just legal ones | ADR aggregate status-transition rules; which transitions emit which events; where status is checked (domain vs router) | Unit test on ADR aggregate (pure domain, no DB) | Only testing legal transitions; implementation-mirror assertions ("status field equals X" copied from aggregate code) |
| 3 | User A's token cannot fetch/update/delete User B's ADR via direct API call with a guessed or enumerated ADR ID | "Authenticated = authorized" — must verify ownership check, not just auth check | How `user_id` scope is enforced in query/command handlers; whether the router or the handler checks ownership | Integration test: two users, cross-access attempt returns 403/404 | Testing only that unauthenticated requests fail (auth != authz) |
| 4 | After save-on-blur fires and the browser is force-closed, reopening the ADR shows the last blurred content; after save-on-unload fires and the tab is refreshed, content is preserved | "The API save endpoint works, so draft loss is impossible" — must test the browser-side trigger (blur/unload) actually fires the save | Frontend save-trigger mechanism; API endpoint for content persistence; what happens when save fails silently | Frontend integration test (blur/unload event → API call assertion) + backend integration test (save endpoint persists correctly) | Testing only the API endpoint without verifying the browser triggers it |
| 5 | When projection update throws after event append, the system either rolls back both or provides a recovery path (replay) | "Same-transaction means atomicity" — must verify the transaction boundary actually wraps both operations | Whether event append and projection update share a DB transaction; what happens on projection error; startup replay behavior | Integration test against real Postgres (append + project in one transaction; simulate projection failure) | Mocking the DB — the risk is specifically about transaction behavior |
| 6 | When the AI review handler raises an unhandled exception, the ADR does not remain stuck in `in_review` — either it transitions to an error state or the event replays on restart | "TaskGroup catches exceptions" — must verify per-task error isolation and the replay mechanism | Event handler error paths; `processed_at` NULL semantics; startup replay logic; whether handler failure marks the event | Integration test: inject a failing handler, verify ADR state after error + after replay | Testing only the happy path where the LLM responds correctly |
| 7 | A request with a tampered JWT (wrong secret, expired, malformed) is rejected with 401; a request with no token to a protected endpoint returns 401 | "JWT library handles validation" — must verify *our* configuration (algorithm, secret, expiry) is correct, not that PyJWT works | Token creation config; middleware/dependency that validates tokens; which endpoints are protected | Unit test on token validation + integration test on protected endpoint | Testing only that a valid token succeeds (proves nothing about rejection) |

## §3 Phased Rollout

| # | Phase name | Goal | Risks covered | Test types | Status | Change folder |
|---|---|---|---|---|---|---|
| 1 | Critical-path domain + auth hardening | Prove ADR lifecycle transitions reject illegal moves and auth/authz boundaries block cross-user access; bootstrap pytest and vitest with meaningful patterns that all later phases follow | 2, 3, 7 | Unit (domain aggregate), integration (API auth + IDOR) | change opened | testing-critical-path-domain-auth |
| 2 | Persistence integrity + event flow | Prove event append + projection atomicity holds under failure and handler crash recovery works; establish DB-backed test fixtures | 5, 6 | Integration (Postgres transactions, handler error injection, startup replay) | not started | — |
| 3 | AI review quality + draft safety | Prove AI review annotation schema and section-detection are correct against fixture ADRs; prove save-on-blur/unload triggers fire and persist content | 1, 4 | Integration (deterministic annotation validation with fixture ADRs), frontend integration (save trigger verification) | not started | — |
| 4 | Quality gates wiring | Lock the test floor: pre-commit hooks run tests, CI runs the full suite, coverage thresholds enforced, test commands documented in AGENTS.md | all | CI/hook configuration | not started | — |

### Phase ordering rationale

- **Phase 1 first:** Risks #2, #3, #7 are testable today (domain aggregate and auth endpoints already exist). These are the cheapest tests for the highest-confidence risks. Establishes the test patterns and fixtures all later phases reuse.
- **Phase 2 second:** Risks #5, #6 require DB fixtures and infrastructure-level testing. Builds on Phase 1's pytest patterns. Must ship before S-04 (AI review) lands to catch event-flow regressions early.
- **Phase 3 third:** Risks #1, #4 depend on S-04 and S-02 being implemented (or nearly so). Tests the product wedge (AI review accuracy) and the "no draft loss" guardrail. The deterministic annotation layer is MVP; probabilistic eval is deferred.
- **Phase 4 last:** All rollout phases must be shippable and green before wiring quality gates. This phase prevents regression by locking the floor.

## §4 Stack

### Backend
- **Language:** Python 3.13+
- **Framework:** FastAPI
- **Test runner:** pytest (configured in `pyproject.toml`, `testpaths = ["tests"]`)
- **Existing test files:** 8 files in `backend/tests/` (domain, application, infrastructure) — generated without a plan, effectively bare
- **Linter/formatter:** Ruff (line-length 88), ty (type checker)
- **Architecture:** Hexagonal, CQRS-lite, event-sourcing-lite

### Frontend
- **Language:** TypeScript
- **Framework:** Nuxt 4
- **Test runner:** Vitest (configured in `vitest.config.ts`, `tests/**/*.test.ts`)
- **Existing test files:** 2 files (`smoke.test.ts`, `auth.store.test.ts`) — minimal, effectively bare
- **Linter/formatter:** ESLint, Prettier, TypeScript (`tsc`)
- **UI library:** shadcn-vue (excluded from test scope)

### Stack grounding tools (current session)
- Docs: Context7 MCP — available; use for Vitest/pytest/Nuxt/FastAPI-specific guidance per rollout phase; checked: 2026-06-16
- Search: Exa.ai MCP — available; use for current tool support and best practices; checked: 2026-06-16
- Runtime/browser: cursor-ide-browser MCP — available; possible e2e verification layer for Phase 3 draft-loss testing; checked: 2026-06-16
- Provider/platform: user-notebooks, user-visualization — not quality-gate relevant; checked: 2026-06-16

## §5 Hot-Spot Evidence

### Scan parameters
- Scope: `backend/` (excluding `.venv`, `__pycache__`, `migrations/versions`), `frontend/app/`
- Period: last 30 days
- Commits in scope: 16

### Top directories by churn
| Directory | Touches (30d) | Risk relevance |
|---|---|---|
| `backend/infrastructure/adapters/persistence/` | 8 | Risk #5 (event/projection atomicity) |
| `backend/domain/user/` | 8 | Risk #7 (auth), Risk #3 (ownership) |
| `backend/application/ports/` | 8 | Risk #5, #6 (port contracts for event store, projections) |
| `frontend/app/components/ui/form/` | 8 | Excluded (shadcn-vue library code) |
| `backend/domain/adr/` | 7 | Risk #2 (status transitions) |
| `frontend/app/pages/` | 6 | Risk #4 (save triggers on ADR editor pages) |

### Signal assessment
16 commits in 30 days is adequate for likelihood calibration. Churn concentrates in persistence adapters and domain layers — consistent with F-02 and S-01 being the only implemented slices. Frontend churn is dominated by UI component scaffolding (shadcn-vue), which is excluded from test scope.

## §6 Cookbook

Test patterns shipped by each rollout phase. Populated as phases complete.

### Phase 1 — Critical-path domain + auth hardening
TBD — see §3 Phase 1 for ADR lifecycle illegal-transition patterns, IDOR cross-user access denial patterns, and JWT rejection patterns.

### Phase 2 — Persistence integrity + event flow
TBD — see §3 Phase 2 for event-append/projection atomicity patterns, handler error injection patterns, and startup replay verification patterns.

### Phase 3 — AI review quality + draft safety
TBD — see §3 Phase 3 for fixture-based annotation schema validation patterns and frontend save-trigger verification patterns.

### Phase 4 — Quality gates wiring
TBD — see §3 Phase 4 for pre-commit hook configuration, CI test suite integration, and coverage threshold enforcement.

## §7 Negative Space

What this plan deliberately excludes — and why. Review quarterly; if the team's beliefs change, re-run `/test-plan --refresh`.

| Area | Why excluded | Revisit when |
|---|---|---|
| shadcn-vue UI components | Library code; testing it tests the library, not application logic (Interview Q5) | Custom components wrap shadcn with business logic |
| Alembic migration files | Run once, verified manually; migration correctness is a deployment concern (Interview Q5) | Migrations become reversible or run in CI against production-like data |
| ORM model definitions | Tested implicitly through integration tests that hit real Postgres (Interview Q5) | Models carry computed properties or custom validation |
| LLM client library wrappers | Test the contract we enforce (annotation schema), not the HTTP client (Interview Q5) | Custom retry/fallback logic is added to the LLM adapter |
| Snapshot tests | Break on every style tweak, catch nothing for a markdown-editor product (Interview Q5) | Visual regression becomes a real risk (e.g. ADR print/export view) |
| Probabilistic AI review eval (F-score) | Expensive; not feasible for MVP; deterministic structural tests cover the contract (Interview Q1 + brief discussion) | Post-MVP when review quality is the competitive moat and prompt iteration is frequent |
| E2E browser tests | Cost × signal: integration tests on API + frontend unit tests cover the same risks cheaper for MVP | Multi-step user flows span >3 pages and integration tests can no longer simulate the interaction |
