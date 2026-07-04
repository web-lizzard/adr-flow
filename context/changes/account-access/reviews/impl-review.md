<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Account Access (S-01)

- **Plan**: context/changes/account-access/plan.md
- **Scope**: Phases 1, 3, 4, 5 of 5
- **Date**: 2026-06-15
- **Verdict**: REJECTED
- **Findings**: 2 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | FAIL |
| Scope Discipline | PASS |
| Safety & Quality | FAIL |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Findings

### F5 — Open redirect via unvalidated login redirect parameter

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/app/pages/login.vue:37-38
- **Detail**: `route.query.redirect` is used verbatim in `navigateTo(redirect)`. An attacker can craft `?redirect=https://evil.com` and the user will be redirected off-site after a successful login (phishing vector).
- **Fix**: Validate that `redirect` is a relative path: starts with `/` and does not start with `//`. Example: `redirect && redirect.startsWith('/') && !redirect.startsWith('//')`.
  - Strength: One-line guard, eliminates the class entirely.
  - Tradeoff: None meaningful.
  - Confidence: HIGH — standard open-redirect mitigation.
  - Blind spot: None significant.
- **Decision**: PENDING

### F6 — No maximum password length allows Argon2 DoS

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/infrastructure/api/schemas/auth.py
- **Detail**: `RegisterRequest` and `LoginRequest` enforce `min_length=8` but no upper bound. Argon2 will hash arbitrarily large inputs (e.g. 1 MB payload), making the endpoint CPU-expensive per request — a trivial DoS vector even without rate limiting.
- **Fix**: Add `max_length=128` to the password field in both `RegisterRequest` and `LoginRequest`.
  - Strength: One-line change per schema, eliminates the class entirely.
  - Tradeoff: None meaningful — 128 chars is generous for passwords.
  - Confidence: HIGH — standard password length cap (bcrypt uses 72, 128 is a safe superset).
  - Blind spot: None significant.
- **Decision**: PENDING

### F1 — Phase 5 unit tests not implemented; progress rubber-stamped

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Plan Adherence + Success Criteria
- **Location**: backend/tests/unit/ (does not exist)
- **Detail**: The plan specifies Phase 5 as "Backend Unit Tests" with: tests/unit/fakes.py (FakeUnitOfWork, FakeEventStore, etc.), tests/unit/test_register_user.py (handler logic with fakes), tests/unit/test_authenticate_user.py (login logic with fakes), tests/unit/test_token_service.py (JWT mint/decode), tests/unit/test_password_hasher.py (argon2 hash/verify). Success criterion: `cd backend && uv run pytest tests/unit/ -v`. None of these exist. The Progress section marks all 4 Phase 5 checkboxes [x] without commit SHAs — the only phase with this gap. What exists instead: 11 integration tests in tests/infrastructure/api/test_auth.py that exercise the same endpoints via TestClient + real Postgres. Behavioral coverage overlaps ~60% but unit isolation (fast feedback without DB, testing handler logic in isolation) is completely absent.
- **Fix A ⭐ Recommended**: Implement the planned unit tests
  - Strength: Achieves the plan's intent — fast (<1s), DB-free tests proving handler logic, password hashing, and JWT independently. Catches regressions that integration tests are too slow to run on every save.
  - Tradeoff: Requires writing ~150 LoC of fakes + 5 test files. Moderate effort.
  - Confidence: HIGH — the integration tests prove the behavior works; unit tests just add speed and isolation.
  - Blind spot: None significant.
- **Fix B**: Accept integration tests as sufficient; update plan
  - Strength: No new code. Existing integration tests already pass and cover the auth pipeline end-to-end.
  - Tradeoff: Loses fast isolated feedback. Test suite requires running Postgres for every run. Future handlers won't have a unit-test pattern to follow.
  - Confidence: MEDIUM — adequate for MVP, but sets a precedent that planning unit tests means nothing.
  - Blind spot: As the codebase grows, integration-only tests become a slow CI bottleneck.
- **Decision**: PENDING

### F2 — Timing oracle enables email enumeration

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/application/queries/authenticate_user.py:33-37
- **Detail**: When the email doesn't exist, the handler returns immediately. When the email exists but password is wrong, it calls password_hasher.verify() (~200ms for argon2). An attacker measuring response times can determine which emails are registered without authentication.
- **Fix A ⭐ Recommended**: Add a dummy verify on unknown email
  - Strength: Constant-time path regardless of email existence. Standard mitigation (Django, Rails both do this).
  - Tradeoff: Adds ~200ms to the "email not found" path.
  - Confidence: HIGH — well-established pattern.
  - Blind spot: Does not protect the /register endpoint which also reveals email existence (400 on duplicate).
- **Fix B**: Accept risk; defer to rate-limiting milestone
  - Strength: Plan explicitly excludes rate limiting from MVP. Email enumeration is low-severity without a password spray vector.
  - Tradeoff: Privacy leak stays until post-MVP hardening.
  - Confidence: MEDIUM — acceptable for MVP if rate limiting lands before production traffic.
  - Blind spot: If rate limiting slips, the oracle persists indefinitely.
- **Decision**: PENDING

### F3 — Unplanned infrastructure files in Phase 3 commit

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: Multiple files (c429a29)
- **Detail**: Phase 3 commit includes files not in the plan: .github/workflows/backend-ci.yml, .devcontainer/devcontainer.json, .devcontainer/post-create.d/20-test-database.sh, .env.example, Justfile, backend/README.md, backend/tests/conftest.py, backend/tests/infrastructure/conftest.py, frontend/app/pages/auth.vue, frontend/app/plugins/ssr-width.ts, frontend/pnpm-workspace.yaml. These are reasonable infra/DX additions that don't violate the plan's intent.
- **Fix**: No action needed — document as accepted scope additions in the plan's Progress section.
- **Decision**: PENDING

### F4 — Auth plugin and test infra added without plan entry

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/app/plugins/auth.ts, frontend/tests/*, frontend/vitest.config.ts
- **Detail**: Phase 4 commit (238f2f6) adds an auth hydration plugin and Vitest test infrastructure (config, setup, auth store test). The plugin is a necessary SSR concern. The test infra supports the auth store tests that Phase 4 success criteria requires. Both are reasonable but unspecified in the plan.
- **Fix**: No action needed — accept as implementation-discovered scope.
- **Decision**: PENDING

## Automated Verification

| Check | Result |
|-------|--------|
| `cd backend && uv run ruff check .` | PASS |
| `cd backend && uv run ty check` | PASS |
| `cd backend && uv run pytest tests/ -v` (27 tests) | PASS |
| Import graph: application/ → infrastructure/ | PASS |
| Import graph: domain/ → application/infrastructure/ | PASS |
| `cd frontend && pnpm run build` | PASS |
| `cd frontend && pnpm run typecheck` | PASS |
| `cd frontend && pnpm run lint` | PASS |
| `cd frontend && pnpm run test` (7 tests) | PASS |
| `cd backend && uv run pytest tests/unit/ -v` | FAIL (directory missing) |

## Notes

- Phase 2 excluded from review (2 manual verification items still unchecked).
- Architecture boundaries are clean: no import graph violations detected.
- The read/write projection split (UserProjection → UserProjection + UserRepository) documented in the Phase 2 addendum is correctly implemented.
- All frontend/backend lint, type, and build checks pass.
- CORS defaults restricted to localhost origins; `allow_methods/headers=["*"]` noted but acceptable for dev.
- JWT secret default clearly labeled "change-me"; pydantic-settings handles env override.
