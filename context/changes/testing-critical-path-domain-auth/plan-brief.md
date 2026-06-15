# Auth Hardening Test Coverage — Plan Brief

> Full plan: `context/changes/testing-critical-path-domain-auth/plan.md`
> Research: `context/changes/testing-critical-path-domain-auth/research.md`

## What & Why

We are implementing a test-only auth hardening rollout to close Risk #7: token forgery/session bypass. The goal is to prove, with deterministic automated coverage, that invalid session tokens are rejected and protected access cannot be bypassed through malformed or forged JWT inputs.

## Starting Point

Auth behavior is implemented and functional today, with most tests concentrated in `backend/tests/infrastructure/api/test_auth.py`. Coverage is currently skewed toward happy paths, with limited rejection vectors and partial cookie-contract verification.

## Desired End State

The backend has complete, maintainable auth security tests spanning JWT decode unit cases, protected endpoint rejection integration cases, cookie-flag assertions, and validation/public-route guards. Risk #7 can be marked resolved because required rejection vectors are explicitly covered and passing.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Phase 1 completion gate | Full 26-case matrix (A+B+C+D) | Full-scope evidence is needed to confidently close Risk #7, not just partial rejection checks. | Research + Plan |
| `nbf` handling | Include as optional non-blocking | It is useful as regression signal but mostly validates library-default behavior rather than app-specific config. | Research + Plan |
| 401 assertion depth | Status + canonical detail text where applicable | This protects against security-significant message drift and supports anti-enumeration guarantees. | Plan |
| Public route checks | Include register/login + health no-cookie accessibility | Hardening should not accidentally lock intentionally public routes. | Plan |
| Deleted-user case | Required in Phase 1 | It validates the full dependency + handler gate where token validity alone must not grant access. | Research + Plan |
| Verification gate style | Targeted unit/auth test files + lint/type checks | This balances fast iteration with sufficient quality controls for each phase. | Plan |

## Scope

**In scope:**
- JWT adapter unit rejection tests.
- `/api/auth/me` protected path rejection integration tests.
- Cookie security attribute assertions for session cookie contract.
- Input-boundary and anti-enumeration checks in auth endpoints.
- Public endpoint no-cookie accessibility checks.

**Out of scope:**
- Logout/revocation infrastructure.
- Login rate limiting or lockout features.
- New endpoint design or auth architecture changes.
- Browser-level CORS behavior simulation.

## Architecture / Approach

The plan follows the existing split between pure unit coverage and full-stack integration coverage. Unit tests directly exercise `JwtTokenService`, while integration tests exercise the production path (`session` cookie -> auth dependency -> handler behavior) through FastAPI `TestClient`, preserving current app wiring and minimizing implementation risk.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. JWT Unit Hardening | Deterministic proof that decode rejects forged/malformed tokens and invalid claims | Flaky time-based token tests if boundaries are too tight |
| 2. Protected Endpoint Rejection Coverage | Full cookie-to-dependency-to-handler rejection proof (including `alg:none` and deleted-user case) | Overfitting tests to library internals instead of app behavior |
| 3. Cookie, Validation, and Public Route Guards | Cookie security contract checks, boundary validation, and public-route safety coverage | Assertion brittleness if response-copy changes are unmanaged |

**Prerequisites:** Existing auth research is complete; backend test environment with Postgres fixture is available.
**Estimated effort:** ~2-3 implementation sessions across 3 phases.

## Open Risks & Assumptions

- Assumes current auth behavior remains unchanged and this effort is test-only.
- `nbf` is treated as optional non-blocking to avoid making third-party defaults a hard release gate.
- Canonical error text assertions assume message copy is part of intended API security contract for this phase.

## Success Criteria (Summary)

- Required forged/invalid token vectors are covered and consistently rejected with expected auth outcomes.
- Public endpoints remain accessible without session cookies after hardening test additions.
- Backend targeted auth tests plus lint/type checks pass with no regressions in existing auth flows.
