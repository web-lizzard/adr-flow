---
project: adr-flow
version: 2
status: active
created: 2026-06-16
updated: 2026-07-05
prd_version: 1
test_base_profile: meaningful (pytest + vitest configured; ~53 backend test modules, 14 frontend test files)
refreshed_by: context/changes/test-plan-refresh-2026-07-05/
---

# Test Plan: adr-flow

> Phased test rollout for ADR Flow. Strategy is frozen at the top (§1–§5);
> cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-07-05

## §1 Strategy

### Principles

1. **Cost × signal.** Every test this rollout adds — classic or AI-native — must answer one question: *what is the cheapest test that gives a real signal for this risk?* Do not promote to e2e because it "feels safer"; do not layer a vision model on top of a deterministic diff that already catches the regression.

2. **User concerns are evidence.** Risks the team has lived through (or fears living through) carry the same weight as PRD lines or hot-spot data.

3. **Risks are scenarios, not code locations.** Every risk in §2 describes a *failure the user would notice*, cited with evidence (PRD lines, interview answers, hot-spot directories). No risk row cites a file path, function name, or schema name as its anchor. Code-level grounding is `/research`'s job, produced per rollout phase against the current codebase.

Hot-spot scope used for likelihood weighting: `backend/` (excluding `.venv`, `__pycache__`, `migrations/versions`), `frontend/app/`.

### North star

The **review process works end-to-end**: login → create ADR → submit for review → receive section ratings and annotations → edit in `after_review` → publish as `proposed`. Auth e2e is required alongside this north-star flow. Phase 3 delivers both with a **mocked LLM** at the API boundary — not a real provider call.

### Negative space — what we do NOT test

- shadcn-vue UI components (library code, not application logic)
- Alembic migration files (run once, verified manually)
- ORM model definitions (tested implicitly through integration)
- LLM client HTTP transport internals (test the contract we enforce)
- Snapshot tests (break on every style tweak, catch nothing for this product)
- Full probabilistic AI review evaluation with F-scores (deferred post-MVP)
- Real-LLM e2e (non-deterministic, expensive, belongs in offline harness only)
- Full browser e2e for every status transition (integration + targeted e2e cover the contract)

## §2 Risk Map

### Top Risks

| # | Risk (failure scenario) | Impact | Likelihood | Source(s) |
|---|---|---|---|---|
| 1 | AI review completes with garbage or empty section ratings — user sees `after_review` but no actionable quality signal, eroding trust in the product wedge | High | High | PRD FR-010 (per-section 0–5 ratings); PRD Business Logic (static + LLM phases); refresh research; hot-spot dir `backend/infrastructure/llm/` (28 touches/30d) |
| 2 | ADR remains stuck in `in_review` after the review worker fails — user waits indefinitely with no recovery path | High | Medium | PRD FR-007/FR-016 (`review_failed` + retry); Architecture: asyncio event dispatch; refresh research |
| 3 | User A can read or modify User B's ADR via direct API call — IDOR; per-user isolation fails | High | Medium | PRD NFR: per-user data isolation; PRD Access Control; hot-spot dir `backend/domain/user/` (prior scan) |
| 4 | Draft content lost on browser refresh, tab close, or session expiry — save-on-blur or save-on-unload silently fails | High | Medium | PRD NFR: no draft loss; PRD FR-006; PRD Open Question #1; hot-spot dir `frontend/app/composables/` (15 touches/30d) |
| 5 | Retry review corrupts state — double retry, stale `review_error`, or duplicate review events leave the ADR in an inconsistent status | High | Medium | PRD FR-016 (retry endpoint); Architecture: event-sourcing-lite idempotency; refresh research |

### Risk Response Guidance

| Risk # | What would prove protection | Must challenge | Context needed | Likely cheapest layer | Anti-pattern to avoid |
|---|---|---|---|---|---|
| 1 | Given fixture ADRs, merged review output always has five section ratings (0–5) with feedback where score ≥ 1, valid annotation kinds, and actionability fields; garbage LLM payloads cannot silently complete as empty `after_review` | "Schema validation exists, so ratings are always good" — validation is currently advisory; must test the *merged API response*, not only wire models | Static + LLM merge rules; `validate_review_result` behavior; fake LLM fixtures; what "complete" means at API boundary | Integration test with injected fake LLM returning malformed/partial payloads | Asserting exact LLM wording; F-score eval as MVP gate; oracle copied from implementation |
| 2 | When the review handler raises (transport error, parse failure, exhausted retries), ADR transitions to `review_failed` with persisted `review_error`; user retry clears error and returns to `in_review` | "TaskGroup catches exceptions" — must verify projection shows `review_failed`, not perpetual `in_review` | Handler failure paths; projection apply; retry command; idempotency on duplicate failure events | Integration test: inject failing LLM service → `review_failed` → retry → `in_review` | Happy-path-only review tests; assuming stuck-in-review is acceptable |
| 3 | User A's token cannot fetch, patch, save, delete, review, or retry User B's ADR | "Authenticated = authorized" — must verify ownership on *mutating* routes, not only GET | How `user_id` scope is enforced in handlers; 403 vs 404 policy | Integration test: two users, cross-access on read + write + retry | Testing only unauthenticated 401; read-path IDOR only |
| 4 | After save-on-blur fires, content persists via API; after save-on-unload/beacon fires on tab close, content survives reload | "The save endpoint works, so draft loss is impossible" — must test blur/unload *triggers* and failure handling | `saveOnBlur` vs `beaconSave`; editor blur wiring; PATCH/beacon API | Frontend unit/integration (blur → store.save) + backend integration (persist) + optional e2e reload | Testing API save without browser triggers; mocking persistence on editor page tests only |
| 5 | Retry from `review_failed` is idempotent; duplicate retry or concurrent submit does not duplicate events or leave stale `review_error` | "Retry endpoint returns 200, so state is correct" — must verify event stream and projection after double-call | Aggregate retry guards; handler skip rules for duplicate `source_event_id`; projection clears `review_error` | Integration test: fail → retry → verify events; double-retry attempt | Testing only single happy retry |

## §3 Phased Rollout

| # | Phase name | Goal | Risks covered | Test types | Status | Change folder |
|---|---|---|---|---|---|---|
| 1 | Critical-path API integration | Close mutating IDOR gaps, persistence API round-trips, and any remaining authz holes on ADR routes — building on existing domain/API coverage rather than bootstrapping from zero | 3, 4 (backend path) | API integration (pytest + TestClient) | shipped | context/changes/testing-critical-path-api-integration/ |
| 2 | AI review contract + error recovery | Prove merged review output contract at API boundary; prove failure → `review_failed` → retry recovery; tighten garbage-rating behavior per product decision | 1, 2, 5 | Integration (fake LLM injection, handler failure, retry idempotency) | not started | — |
| 3 | E2E auth + north-star review (mocked LLM) | Prove register/login → workspace and full review north star in a real browser with LLM mocked at API — the user's definition of "it works" | 1, 2, 4 (frontend path) | E2E (Playwright or Vitest browser — bootstrap in this phase) | not started | — |
| 4 | Quality gates wiring | Lock the test floor: pre-commit runs tests, CI runs full suite, test commands documented; coverage thresholds if justified | all | CI/hook configuration | not started | — |

### Phase ordering rationale

- **Phase 1 first:** Existing suite already covers domain lifecycle and read-path IDOR. Cheapest remaining signal is mutating cross-user API tests and backend persistence — reuses current pytest fixtures.
- **Phase 2 second:** AI review contract and recovery are the product wedge. Fake-LLM integration tests extend the `review_quality/` harness to the API boundary before browser cost.
- **Phase 3 third:** North-star e2e requires auth + review UI + persistence triggers together; mocked LLM keeps CI deterministic. Bootstrap e2e runner here, not before API gaps close.
- **Phase 4 last:** Gates lock a green suite; wiring before Phases 1–3 would block on incomplete coverage.

## §4 Stack

### Backend
- **Language:** Python 3.13+
- **Framework:** FastAPI
- **Test runner:** pytest 9.x (`pyproject.toml`, `testpaths = ["tests"]`)
- **Existing test files:** ~53 modules under `backend/tests/` (domain, application, API, review_quality, persistence, auth)
- **Linter/formatter:** Ruff (line-length 88), ty (type checker)
- **Architecture:** Hexagonal, CQRS-lite, event-sourcing-lite

### Frontend
- **Language:** TypeScript
- **Framework:** Nuxt 4
- **Test runner:** Vitest (`vitest.config.ts`, `frontend/tests/**/*.test.ts`)
- **Existing test files:** 14 files (auth, adr store, persistence composable, review UI components, editor page)
- **Linter/formatter:** ESLint, Prettier, TypeScript (`tsc`)
- **UI library:** shadcn-vue (excluded from test scope)

### E2E
- **Runner:** none yet — see §3 Phase 3
- **Recommendation:** Playwright (aligns with cursor-ide-browser MCP for local debugging) or Vitest browser mode if team prefers single runner

| Layer | Tool | Version | Notes |
|---|---|---|---|
| unit + integration (backend) | pytest + httpx | 9.x | API tests use `AsyncClient` against app factory |
| unit + integration (frontend) | Vitest + jsdom | 4.x | Component tests use `@vue/test-utils` |
| API mocking (frontend e2e) | Playwright route intercept / MSW | TBD | Mock LLM at API boundary in Phase 3 |
| e2e | Playwright (planned) | TBD | Bootstrap in Phase 3 — north star + auth |
| accessibility | none | — | Not in MVP rollout scope |

### Stack grounding tools (current session)
- Docs: Context7 MCP — available; use for Vitest/pytest/Playwright setup per phase; checked: 2026-07-05
- Search: Exa.ai MCP — available; use for current Playwright/Nuxt test guidance; checked: 2026-07-05
- Runtime/browser: cursor-ide-browser MCP — available; local verification aid for Phase 3 e2e; checked: 2026-07-05
- Provider/platform: GCP observability MCP — not quality-gate relevant for MVP; checked: 2026-07-05

## §5 Quality Gates

| Gate | Where | Required? | Catches |
|---|---|---|---|
| lint + typecheck | local + pre-commit | required | syntactic / type drift |
| unit + integration (backend) | local + CI | required after §3 Phase 2 | API and domain regressions |
| unit + integration (frontend) | local + CI | required after §3 Phase 2 | store/composable/component regressions |
| e2e north-star + auth | CI on PR | required after §3 Phase 3 | broken review flow or auth redirect |
| pre-commit test hook | local (agent loop) | recommended after §3 Phase 4 | regressions at edit time |
| coverage thresholds | CI | optional after §3 Phase 4 | untested new code in hot paths |

## §6 Cookbook

Test patterns shipped by each rollout phase. Populated as phases complete.

### Phase 1 — Critical-path API integration

Shipped in `context/changes/testing-critical-path-api-integration/`. File: `backend/tests/infrastructure/api/test_adr_api.py`.

#### Mutating IDOR denial (Risk #3)

**Behavior:** User B's Bearer token cannot mutate User A's ADR on write routes; API returns **404** (not 403) and owner state is unchanged.

**Pattern:**

1. Owner registers → `set_bearer_auth` → create ADR with known `title` / `content`
2. `clear_bearer_auth` → intruder registers → `set_bearer_auth`
3. Intruder calls mutating route → assert `status_code == 404`
4. Switch back to owner token → `GET /api/adrs/{id}` → assert `title`, `content`, or `status` unchanged

**Routes covered:** `PATCH /api/adrs/{id}`, `POST /api/adrs/{id}/save`, `POST /api/adrs/{id}/retry-review` (draft seed suffices — owner check runs before status validation).

**Tests:** `test_patch_returns_404_for_other_users_adr`, `test_beacon_save_returns_404_for_other_users_adr`, `test_retry_review_returns_404_for_other_users_adr` (plus existing read/submit/publish/delete cross-user tests).

**Helpers:** `register_and_get_token`, `set_bearer_auth`, `clear_bearer_auth` from `backend/tests/infrastructure/api/conftest.py`; mirror `test_accessing_another_users_adr_returns_404`.

**Anti-pattern:** Testing only unauthenticated 401 or read-path IDOR (`GET`, list, search) without mutating-route denial.

#### Persistence API round-trip (Risk #4, backend path)

**Behavior:** Content saved via the beacon unload path survives an independent read — projection/write failure cannot hide behind a 204 response.

**Pattern:**

1. Authenticated user creates ADR
2. `POST /api/adrs/{id}/save` with `{"content": "<payload>"}` → assert `204`
3. `GET /api/adrs/{id}` → assert `content == "<payload>"` (oracle is the GET, not the save response body)

**Tests:** `test_get_after_beacon_save_returns_updated_content` (PATCH round-trip: `test_get_after_patch_returns_updated_content`).

**Anti-pattern:** Asserting `204`/`200` on save or PATCH without a separate GET to prove persistence.

### Phase 2 — AI review contract + error recovery
TBD — see §3 Phase 2 for fake-LLM injection patterns, garbage-rating rejection or documented acceptance, and `review_failed` → retry recovery patterns.

### Phase 3 — E2E auth + north-star review (mocked LLM)
TBD — see §3 Phase 3 for Playwright auth flow patterns and north-star review flow with API-level LLM mock.

### Phase 4 — Quality gates wiring
TBD — see §3 Phase 4 for pre-commit test integration, CI workflow, and documented `just test` usage in AGENTS.md.

### Existing reference tests (pre-rollout baseline)

Contributors can study these before Phase 1 ships cookbook entries:

- Domain lifecycle illegal transitions: `backend/tests/domain/test_adr_aggregate.py`
- API read-path IDOR + review happy path: `backend/tests/infrastructure/api/test_adr_api.py`
- Review schema + runtime validation: `backend/tests/review_quality/`, `backend/tests/domain/adr/test_review_llm_schema.py`
- Frontend review UI (mocked): `frontend/tests/adr-editor-page.test.ts`
- Unload beacon persistence: `frontend/tests/useAdrPersistence.test.ts`

## §7 Negative Space

What this plan deliberately excludes — and why. Review quarterly; if beliefs change, re-run `/test-plan --refresh`.

| Area | Why excluded | Revisit when |
|---|---|---|
| shadcn-vue UI components | Library code; tests the library, not application logic | Custom components wrap shadcn with business logic |
| Alembic migration files | Run once, verified manually | Migrations run in CI against production-like data |
| ORM model definitions | Covered implicitly through Postgres integration tests | Models carry computed properties or custom validation |
| LLM HTTP client internals | Test enforced contract (ratings + annotations), not transport | Custom retry/fallback logic added to adapter |
| Snapshot tests | Break on style tweaks; low signal for markdown editor | Print/export view needs visual regression |
| Probabilistic AI eval (F-score) | Expensive; offline harness only post-MVP | Review quality is competitive moat and prompts iterate weekly |
| Real-LLM e2e | Non-deterministic, costly, flaky in CI | Scheduled nightly job with budget cap |
| Full browser e2e for every status transition | Cost × signal: API + unit tests cover illegal transitions | Multi-page flows exceed integration simulation |
| Event/projection atomicity under failure | Deprioritized vs north-star; add if persistence incidents occur | Production stale-read incident or replay bug |

## §8 Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-07-05
- Stack versions last verified: 2026-07-05
- AI-native tool references last verified: 2026-07-05

Refresh (`/test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.

Prior refresh: `context/changes/test-plan-refresh-2026-07-05/` (product pivot to LLM ratings, test base sparse → meaningful, §3 phases reset).
