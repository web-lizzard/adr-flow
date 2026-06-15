---
date: 2026-06-16T01:15:00+02:00
researcher: AI
git_commit: bf155ce3ad7b63ef34bf7af3c5896030158bb3e1
branch: main
repository: adr-flow
topic: "Test cases for Phase 1: Auth hardening — resolving Risk #7"
tags: [research, codebase, testing, auth, jwt, cookie, token-service, risk-7]
status: complete
last_updated: 2026-06-16
last_updated_by: AI
last_updated_note: "Refocused exclusively on Risk #7 auth cases resolvable today"
---

# Research: Auth Test Cases to Resolve Risk #7

**Date**: 2026-06-16T01:15:00+02:00
**Researcher**: AI
**Git Commit**: bf155ce3ad7b63ef34bf7af3c5896030158bb3e1
**Branch**: main
**Repository**: adr-flow

## Research Question

What test cases must Phase 1 cover to **fully resolve** Risk #7 (auth token forgery / session bypass) from the test plan risk map? Focus only on auth — the endpoints exist today.

## Summary

Risk #7 states: *"JWT validation is weak, allowing unauthenticated or cross-user access."* The risk response guidance says:

> **What would prove protection:** A request with a tampered JWT (wrong secret, expired, malformed) is rejected with 401; a request with no token to a protected endpoint returns 401.
> **Must challenge:** "JWT library handles validation" — must verify *our* configuration (algorithm, secret, expiry) is correct, not that PyJWT works.
> **Anti-pattern to avoid:** Testing only that a valid token succeeds (proves nothing about rejection).

The existing 11 tests cover **only happy paths and one missing-cookie case**. No rejection vectors are tested. To resolve Risk #7, we need:

1. **Unit tests on `JwtTokenService`** — prove that our decode rejects every forgery class (9 cases)
2. **Integration tests on the cookie→dependency→handler stack** — prove the full HTTP path rejects invalid sessions (8 cases)
3. **Cookie security attribute tests** — prove our configuration produces correct cookie flags (4 cases)
4. **Input validation boundary tests** — prove auth endpoints reject malformed inputs without leaking information (5 cases)

Total: **26 new test cases** (none require new endpoints or features — all testable against today's code).

---

## Detailed Findings

### What Already Exists (Coverage Baseline)

| # | Case | File | Verdict |
|---|---|---|---|
| 1 | Register → 201 + cookie set | `test_auth.py:11` | Happy path only |
| 2 | Cookie path = `/api` | `test_auth.py:25` | One attribute only |
| 3 | Duplicate email → 400 | `test_auth.py:47` | Domain error, not auth |
| 4 | Login correct → 200 + cookie | `test_auth.py:57` | Happy path only |
| 5 | Login wrong password → 401 | `test_auth.py:73` | **Partial rejection** |
| 6 | Login case-insensitive email | `test_auth.py:87` | Normalization, not auth |
| 7 | `/me` valid cookie → 200 | `test_auth.py:102` | Happy path only |
| 8 | `/me` no cookie → 401 | `test_auth.py:114` | **Partial rejection** |
| 9-11 | Event/projection persistence | `test_auth.py:119-161` | Data integrity, not auth |

**Gap analysis:** Only cases 5 and 8 test rejection. The test plan's "must challenge" is: *does our JWT config reject forgery?* None of the 11 tests verify this.

---

### Category A: JwtTokenService Unit Tests (Pure, No DB/HTTP)

These prove that `decode_token` in `token_service.py:24-41` rejects every JWT forgery class. They test **our** algorithm lock (`HS256`), our secret binding, and our claim validation — not PyJWT internals.

| # | Case | Input | Expected | What it proves |
|---|---|---|---|---|
| A1 | Valid round-trip | `create_token(uuid)` → `decode_token(result)` | Same UUID | Baseline sanity |
| A2 | Expired token | Token with `exp` in the past | `None` | Our 24h expiry actually rejects |
| A3 | Wrong signing secret | Token signed with secret A, decoded with secret B | `None` | Secret mismatch = rejection |
| A4 | Malformed token string | `"not.a.jwt.at.all"` | `None` | Garbage doesn't crash |
| A5 | Empty string token | `""` | `None` | Edge case handling |
| A6 | Tampered payload | Flip bits in the encoded payload section | `None` | Signature verification active |
| A7 | Missing `sub` claim | `jwt.encode({"exp": future}, secret, "HS256")` | `None` | Our `payload.get("sub")` check |
| A8 | Non-UUID `sub` claim | `jwt.encode({"sub": "not-a-uuid", "exp": future}, ...)` | `None` | Our `UUID(sub)` parse check |
| A9 | Non-string `sub` claim | `jwt.encode({"sub": 12345, "exp": future}, ...)` | `None` | Our `isinstance(sub, str)` check |

**Implementation note for A2:** `JwtTokenService` takes `expiry_hours` as constructor arg. Create instance with `expiry_hours=0` — the resulting token has `exp ≈ now` which should be expired by decode time. Alternative: use `jwt.encode` directly with explicit past `exp`.

**Implementation note for A6:** Take a valid token string, base64-decode the payload segment, change one byte, re-encode — the signature no longer matches.

---

### Category B: Protected Endpoint Integration Tests (Cookie→Dependency→Handler)

These prove the full HTTP stack — `get_current_user_id` dependency in `dependencies.py:36-48` and the `/me` handler — rejects invalid sessions via real HTTP with real Postgres.

| # | Case | Request setup | Expected | What it proves |
|---|---|---|---|---|
| B1 | Tampered cookie value | Set `session` cookie to `"garbage-string"` | HTTP 401 | Dependency catches decode failure |
| B2 | Expired cookie | Set `session` cookie to token with past `exp` | HTTP 401 | Expiry enforced at HTTP level |
| B3 | Wrong-secret cookie | Create token with different secret, set as cookie | HTTP 401 | Secret mismatch blocks at HTTP |
| B4 | Valid token for deleted user | Register → delete user row → call `/me` | HTTP 401 | `UserNotFound` → 401 mapping (line 109 in router) |
| B5 | Algorithm confusion (alg:none) | `jwt.encode({"sub": uuid, "exp": future}, "", algorithm="none")` as cookie | HTTP 401 | `algorithms=["HS256"]` lock in decode |
| B6 | Token with future `nbf` (not-before) | Token with `nbf` claim set to far future | HTTP 401* | PyJWT rejects tokens not yet valid |
| B7 | Public endpoints without cookie | `POST /auth/register`, `POST /auth/login` | HTTP 2xx | No auth required on public routes |
| B8 | Health endpoints without cookie | `GET /health`, `GET /api/health` | HTTP 200 | Health checks are public |

*B6 note: PyJWT validates `nbf` by default when present. This ensures we haven't disabled it.*

---

### Category C: Cookie Security Attribute Tests

These prove our `_set_session_cookie` in `routers/auth.py:114-127` produces correct security flags. The risk is misconfiguration — a missing `httponly` or wrong `samesite` could allow XSS token theft or CSRF.

| # | Case | How to verify | Expected | What it proves |
|---|---|---|---|---|
| C1 | Cookie is HttpOnly | Parse `Set-Cookie` header after login | Contains `HttpOnly` | XSS can't read token via JS |
| C2 | Cookie SameSite=Lax | Parse `Set-Cookie` header | Contains `SameSite=lax` | CSRF mitigation active |
| C3 | Cookie max-age = 86400 | Parse `Set-Cookie` header | Contains `Max-Age=86400` | Cookie expires with token |
| C4 | Cookie Secure flag respects config | Create app with `cookie_secure=True`, check header | Contains `Secure` | HTTPS enforcement works when enabled |

**Implementation note:** `TestClient` allows reading raw `Set-Cookie` headers via `response.headers.get("set-cookie")`. Parse the header string for flag presence.

---

### Category D: Input Validation Boundary Tests (Information Leakage Prevention)

These prove auth endpoints reject malformed input **without revealing** whether a user exists (timing oracle / error message enumeration).

| # | Case | Input | Expected | What it proves |
|---|---|---|---|---|
| D1 | Login with non-existent email | Valid format, unknown email | HTTP 401, same message as wrong password | No user enumeration via different error |
| D2 | Login with invalid email format | `"not-an-email"` | HTTP 422 (Pydantic `EmailStr` rejects) | Input validation before handler |
| D3 | Register with password < 8 chars | `{"email": "a@b.com", "password": "short"}` | HTTP 422 | Length guard active |
| D4 | Register with exactly 8 char password | `{"email": "a@b.com", "password": "exactly8"}` | HTTP 201 | Boundary passes |
| D5 | Register with empty password | `{"email": "a@b.com", "password": ""}` | HTTP 422 | Empty rejected |

**Why these resolve Risk #7:** An attacker probing auth endpoints should get uniform responses that don't leak whether accounts exist. Case D1 is critical — `authenticate_user.py:33-37` returns `InvalidCredentials` for both "user not found" and "wrong password", which the router maps to the same 401 message.

---

## Architecture Insights Relevant to Testing

### 1. Cookie-based auth, not Bearer headers
No `Authorization` header is ever read. Tests must set the `session` cookie, not an `Authorization` header. The existing `auth_client` fixture in `conftest.py` uses `TestClient` which automatically handles cookies across requests.

### 2. Single protected endpoint today: `/api/auth/me`
This is the only route using `Depends(get_current_user_id)`. All token rejection tests go through this endpoint. When ADR endpoints ship (S-02+), they'll reuse the same dependency — so proving it rejects here proves it rejects everywhere.

### 3. `get_current_user_id` is the auth gate
The dependency at `dependencies.py:36-48` is the single enforcement point:
1. Missing cookie → 401
2. `decode_token()` returns `None` → 401
3. Returns `UUID` (caller is authenticated)

The handler then checks if the user exists (`UserNotFound` → 401). This two-step means a valid token for a deleted user still fails.

### 4. No logout or token revocation
Tokens are valid until `exp` (24h). No blacklist exists. This is acceptable for MVP (noted in architecture insights) but means:
- A stolen token is valid for its full lifetime
- Tests should NOT assume token invalidation after any action

### 5. Algorithm locked to HS256
`decode_token` passes `algorithms=["HS256"]` — this prevents the classic `alg:none` attack where an attacker sets the algorithm header to "none" and skips signature verification. Test B5 verifies this.

### 6. CORS + credentials
Bootstrap configures `allow_credentials=True` with explicit `allow_origins`. This means:
- Cross-origin requests CAN include the session cookie
- But only from origins in the `cors_origins` list
- Combined with `samesite="lax"`, this prevents CSRF from arbitrary origins
- CORS enforcement is browser-side; API-level tests can't truly verify it (browser enforces preflight). Cookie attribute tests (Category C) are the proxy.

---

## Code References

- `backend/infrastructure/adapters/auth/token_service.py:11-41` — `JwtTokenService`: `create_token` (line 16-22), `decode_token` (line 24-41)
- `backend/infrastructure/api/dependencies.py:36-48` — `get_current_user_id`: cookie extraction + decode + 401
- `backend/infrastructure/api/routers/auth.py:44-73` — Register endpoint (public, sets cookie)
- `backend/infrastructure/api/routers/auth.py:75-98` — Login endpoint (public, sets cookie)
- `backend/infrastructure/api/routers/auth.py:100-111` — `/me` endpoint (protected, `UserNotFound` → 401)
- `backend/infrastructure/api/routers/auth.py:114-127` — `_set_session_cookie` (httponly, secure, samesite, path, max_age)
- `backend/infrastructure/api/schemas/auth.py:9-19` — `RegisterRequest` with password min-length 8
- `backend/infrastructure/api/schemas/auth.py:22-24` — `LoginRequest` with password min-length 1
- `backend/infrastructure/config.py:21-27` — `jwt_secret`, `cookie_secure`, `cookie_path` from env
- `backend/infrastructure/bootstrap.py:64-70` — CORS middleware with `allow_credentials=True`
- `backend/application/queries/authenticate_user.py:27-38` — Uniform `InvalidCredentials` for email/password failures
- `backend/application/queries/get_current_user.py:17-21` — `UserNotFound` when ID not in projection

---

## Test File Layout (Proposed)

```
backend/tests/
├── unit/
│   └── auth/
│       └── test_jwt_token_service.py    ← Category A (9 cases, pure unit)
└── infrastructure/
    └── api/
        └── test_auth.py                 ← Categories B, C, D (17 cases, extend existing file)
```

**Rationale:**
- Category A is a pure unit test — no DB, no HTTP, no fixtures. Lives in `tests/unit/auth/`.
- Categories B, C, D are integration tests that need the full app + Postgres. They extend the existing `test_auth.py` and reuse the `auth_client` fixture.

---

## Risk Resolution Checklist

After all 26 cases pass, the following from the risk response guidance will be **proven**:

| Risk #7 requirement | Proved by |
|---|---|
| Tampered JWT rejected with 401 | A3, A6, B1, B3 |
| Expired JWT rejected with 401 | A2, B2 |
| Malformed JWT rejected with 401 | A4, A5, B1 |
| No token → 401 on protected endpoint | Existing test (case 8) |
| Our algorithm config is correct (not just PyJWT default) | A3 (secret), B5 (alg:none) |
| Our expiry config is correct | A2 (unit), B2 (integration) |
| Cookie security attributes prevent XSS/CSRF | C1, C2, C3, C4 |
| No user enumeration via error messages | D1 |
| Valid token for non-existent user fails | B4 |

**What's NOT in scope** (deferred per negative space):
- Token revocation / logout — not implemented, not MVP
- Rate limiting on login attempts — infrastructure concern, not auth correctness
- CORS enforcement testing — browser-enforced, can't be API-tested meaningfully
- Password strength beyond min-length — UX concern, not a security boundary test

---

## Open Questions

1. **B5 feasibility:** PyJWT may raise an error before checking `algorithms` if `algorithm="none"` is used with an empty key. Need to verify the exact `jwt.encode` call that produces an `alg:none` token. If PyJWT refuses to create one, use raw base64 construction.

2. **B6 relevance:** The `nbf` (not-before) claim isn't used by our `create_token`, but an attacker could inject it. PyJWT validates it by default — do we want to explicitly prove this, or is it testing PyJWT behavior? **Recommendation:** Include it — it costs one test and proves we haven't accidentally disabled claim validation via `options` parameter.
