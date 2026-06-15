# Auth Hardening Test Coverage Implementation Plan

## Overview

Implement comprehensive auth-focused test coverage to resolve Risk #7 (token forgery/session bypass) in Phase 1 without changing runtime auth behavior. The plan adds missing negative-path tests across JWT decoding, protected endpoint enforcement, cookie security attributes, and input-boundary behavior.

## Current State Analysis

Auth tests currently validate primary happy paths and only minimal rejection cases. Core security behavior exists in code, but its rejection guarantees are not yet fully proven by tests.

## Desired End State

A full, reliable test matrix proves that invalid or forged auth sessions are rejected with `401`, public endpoints remain accessible, and cookie/security input contracts stay intact. Risk #7 is considered resolved when the defined automated checks pass and manual verification confirms no auth regression in expected user flows.

### Key Discoveries:

- Auth enforcement is centralized in `backend/infrastructure/api/dependencies.py` and token decoding in `backend/infrastructure/adapters/auth/token_service.py`.
- Existing integration coverage is concentrated in `backend/tests/infrastructure/api/test_auth.py` and lacks forged-token vectors.
- Cookie flags are set in `backend/infrastructure/api/routers/auth.py` but only cookie path is currently asserted.
- PyJWT is pinned in `backend/uv.lock`, and `HS256` allowlist lock is enforced by the adapter.

## What We're NOT Doing

- Implementing logout, token revocation, or blacklist infrastructure.
- Adding login rate limiting or anti-bruteforce controls.
- Introducing auth middleware redesign or new protected routes.
- Changing existing endpoint contracts or response schemas beyond test assertions.

## Implementation Approach

Use an incremental test-only rollout in three phases:
1) add deterministic unit tests around JWT decode behavior,
2) extend integration tests around cookie-to-dependency-to-handler rejection paths,
3) add security-attribute and boundary checks plus public-route guards.

This keeps risk closure explicit, minimizes behavioral change risk, and mirrors existing backend testing conventions.

## Critical Implementation Details

Use time-buffered token construction for expiry tests (for example, clearly past and future timestamps) to avoid flaky boundary timing. Treat `nbf` as optional non-blocking coverage: include it as a regression guard, but do not gate phase completion on that case because it primarily validates library-default behavior.

## Phase 1: JWT Unit Hardening

### Overview

Add unit tests that directly prove `JwtTokenService.decode_token` rejects forgery classes and malformed claims.

### Changes Required:

#### 1. JWT token service unit tests

**File**: `backend/tests/unit/auth/test_jwt_token_service.py`

**Intent**: Add isolated tests for decode behavior independent from HTTP and database fixtures. This phase establishes core cryptographic/session validity guarantees at the adapter boundary.

**Contract**: Validate round-trip success and rejection for expired tokens, wrong-secret tokens, malformed token strings, tampered token content, missing `sub`, non-string `sub`, and non-UUID `sub`.

### Success Criteria:

#### Automated Verification:

- Unit auth token tests pass in `backend/tests/unit/auth/test_jwt_token_service.py`.
- Existing backend auth integration tests still pass in `backend/tests/infrastructure/api/test_auth.py`.
- Ruff checks pass for backend with `uv run ruff check .`.
- Type checks pass for backend with `uv run ty check`.

#### Manual Verification:

- Team review confirms each JWT rejection class in Risk #7 has a direct unit assertion.
- Team review confirms token-time assertions are deterministic and non-flaky.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Protected Endpoint Rejection Coverage

### Overview

Extend integration tests to prove the full cookie-to-dependency-to-handler path rejects invalid session states with expected `401` behavior.

### Changes Required:

#### 1. Auth integration rejection cases

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Add rejection-focused `/api/auth/me` tests that exercise real HTTP and auth dependency wiring. This phase proves session bypass attempts fail through the production path.

**Contract**: Cover tampered cookie, malformed cookie, expired token cookie, wrong-secret cookie, `alg:none` cookie, and valid-token-for-deleted-user yielding `401`.

#### 2. Optional non-blocking `nbf` guard

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Add a single not-before (`nbf`) negative test as a regression guard while keeping it outside blocking phase exit.

**Contract**: If present, token with future `nbf` should be rejected by auth dependency path with `401`.

### Success Criteria:

#### Automated Verification:

- Added protected-endpoint rejection tests pass in `backend/tests/infrastructure/api/test_auth.py`.
- Existing happy-path auth tests remain green in `backend/tests/infrastructure/api/test_auth.py`.
- Ruff checks pass for backend with `uv run ruff check .`.
- Type checks pass for backend with `uv run ty check`.

#### Manual Verification:

- Team review confirms all required rejection vectors map to Risk #7 closure criteria.
- Team review confirms optional `nbf` behavior is clearly labeled as non-blocking in test comments and plan tracking.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Cookie, Validation, and Public Route Guards

### Overview

Add tests that enforce cookie security attributes, anti-enumeration boundary behavior, and public endpoint accessibility.

### Changes Required:

#### 1. Cookie security attribute assertions

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Ensure the auth cookie contract remains secure and stable across future refactors.

**Contract**: Assert `HttpOnly`, `SameSite=lax`, `Max-Age=86400`, and `Secure` behavior when app is configured with `cookie_secure=True`.

#### 2. Input boundary and anti-enumeration tests

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Ensure malformed auth inputs are rejected correctly and login failures do not leak user existence.

**Contract**: Add non-existent-email login parity checks and request-validation boundaries for invalid email and password length constraints.

#### 3. Public route accessibility checks

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Ensure auth hardening does not accidentally lock public endpoints.

**Contract**: Verify register/login and health endpoints remain accessible without session cookies.

### Success Criteria:

#### Automated Verification:

- Cookie attribute, validation-boundary, and public-route tests pass in `backend/tests/infrastructure/api/test_auth.py`.
- Unit auth token tests remain green in `backend/tests/unit/auth/test_jwt_token_service.py`.
- Ruff checks pass for backend with `uv run ruff check .`.
- Type checks pass for backend with `uv run ty check`.

#### Manual Verification:

- Team review confirms error assertions enforce canonical auth semantics (`Not authenticated`, `Invalid email or password`) where applicable.
- Team review confirms no accidental tightening of public endpoint behavior.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Token create/decode round-trip and deterministic negative decode behavior.
- Claim-structure boundaries (`sub` shape and UUID validity).
- Signature and secret mismatch rejection.

### Integration Tests:

- Protected endpoint rejection via real cookie injection and dependency execution.
- Valid-token-but-missing-user rejection path.
- Cookie flag contract assertions and public endpoint accessibility.

### Manual Testing Steps:

1. Run focused backend tests for new unit and auth integration files.
2. Confirm `401` behavior/messages on negative auth flows and unchanged success flows.
3. Confirm public routes still respond without auth cookies.

## Performance Considerations

Test additions are lightweight and should not materially affect runtime performance. To keep CI feedback fast, phase gates use targeted test files plus backend lint/type checks.

## Migration Notes

No schema or data migration is required. This is a test-only plan.

## References

- Related research: `context/changes/testing-critical-path-domain-auth/research.md`
- Change metadata: `context/changes/testing-critical-path-domain-auth/change.md`
- Auth token adapter: `backend/infrastructure/adapters/auth/token_service.py`
- Auth dependency and router: `backend/infrastructure/api/dependencies.py`, `backend/infrastructure/api/routers/auth.py`
- Current auth tests: `backend/tests/infrastructure/api/test_auth.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: JWT Unit Hardening

#### Automated

- [x] 1.1 Unit auth token tests pass in `backend/tests/unit/auth/test_jwt_token_service.py`
- [x] 1.2 Existing backend auth integration tests still pass in `backend/tests/infrastructure/api/test_auth.py`
- [x] 1.3 Ruff checks pass for backend with `uv run ruff check .`
- [x] 1.4 Type checks pass for backend with `uv run ty check`

#### Manual

- [x] 1.5 Team review confirms each JWT rejection class in Risk #7 has a direct unit assertion
- [x] 1.6 Team review confirms token-time assertions are deterministic and non-flaky

### Phase 2: Protected Endpoint Rejection Coverage

#### Automated

- [ ] 2.1 Added protected-endpoint rejection tests pass in `backend/tests/infrastructure/api/test_auth.py`
- [ ] 2.2 Existing happy-path auth tests remain green in `backend/tests/infrastructure/api/test_auth.py`
- [ ] 2.3 Ruff checks pass for backend with `uv run ruff check .`
- [ ] 2.4 Type checks pass for backend with `uv run ty check`

#### Manual

- [ ] 2.5 Team review confirms all required rejection vectors map to Risk #7 closure criteria
- [ ] 2.6 Team review confirms optional `nbf` behavior is clearly labeled as non-blocking in test comments and plan tracking

### Phase 3: Cookie, Validation, and Public Route Guards

#### Automated

- [ ] 3.1 Cookie attribute, validation-boundary, and public-route tests pass in `backend/tests/infrastructure/api/test_auth.py`
- [ ] 3.2 Unit auth token tests remain green in `backend/tests/unit/auth/test_jwt_token_service.py`
- [ ] 3.3 Ruff checks pass for backend with `uv run ruff check .`
- [ ] 3.4 Type checks pass for backend with `uv run ty check`

#### Manual

- [ ] 3.5 Team review confirms error assertions enforce canonical auth semantics (`Not authenticated`, `Invalid email or password`) where applicable
- [ ] 3.6 Team review confirms no accidental tightening of public endpoint behavior
