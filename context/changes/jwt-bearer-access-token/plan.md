# JWT Bearer Access Token Implementation Plan

## Overview

Migrate authentication transport from httponly `session` cookie to JWT `access_token` returned in login/register response bodies and sent via `Authorization: Bearer` on protected API calls. Domain logic, password hashing, JWT mint/verify (`JwtTokenService`), 24h expiry, and per-user isolation semantics stay unchanged. No refresh token, no logout endpoint.

## Current State Analysis

Auth is **transport-only wrong** — the backend already mints HS256 JWTs on register/login but writes them to an httponly cookie; `get_current_user_id` reads `request.cookies.get("session")`. All 11 protected endpoints funnel through that single dependency.

| Layer | Today |
|-------|-------|
| `JwtTokenService` | HS256, `sub` + `exp` (24h) — **unchanged** |
| `auth.py` register/login | Mint JWT → `_set_session_cookie` → return `UserResponse` |
| `dependencies.py` | Cookie read → `decode_token` |
| Frontend auth store | In-memory `user` only; plain `$fetch`, no token |
| Frontend ADR API | Nine protected `$fetch` helpers in `useApi.ts`, no auth headers |
| Unload save | `sendBeacon` + cookie fallback — **breaks under Bearer** |
| SSR bootstrap | `plugins/auth.ts`, middleware, `index.vue` call `fetchUser()` on server |

### Key Discoveries:

- Single dependency swap updates all protected routes — `backend/infrastructure/api/dependencies.py:96-110`
- Cookie writes exist only in `auth.py:_set_session_cookie` — `backend/infrastructure/api/routers/auth.py:133-146`
- `COOKIE_SECURE` / `COOKIE_PATH` are used exclusively by cookie setting — removable from `config.py`, deploy, devcontainer
- Deleted-user 401 is `/me`-only today (`UserNotFound` catch in `auth.py:127-128`); ADR routes accept valid JWT for deleted users until `exp` — **keep existing asymmetry** (out of scope)
- Nitro proxy forwards headers transparently — no proxy changes needed
- `SESSION_MAX_AGE_SECONDS` in `auth.py` duplicates `JwtTokenService` 24h default — remove with cookie helper

## Desired End State

- Register/login return `{ access_token }` (`AuthResponse`); no `Set-Cookie`; user profile via `GET /auth/me`
- Protected routes require `Authorization: Bearer <token>`; missing/invalid token → 401 `"Not authenticated"`
- Frontend stores token in `sessionStorage`, attaches on all protected API calls via central `apiFetch`
- 401 on protected calls clears token + user state and redirects to `/login`
- Auth hydration runs client-only; SSR does not attempt cookie-less Bearer calls
- Unload save uses `fetch` + `keepalive` + `Authorization` (no `sendBeacon`)
- `COOKIE_*` env vars removed from config, deploy scripts, devcontainer, docs
- All backend and frontend tests assert Bearer contract

### Verification:

1. Register → response body contains `access_token`; no session cookie
2. `GET /api/auth/me` with Bearer token → 200 user
3. `GET /api/auth/me` without header → 401
4. Login → same; token usable on ADR endpoints
5. Browser: login, refresh page, workspace loads (sessionStorage)
6. Close tab, reopen → must re-login (sessionStorage cleared)
7. Edit ADR, close tab quickly → blur/unload save persists draft (keepalive path)
8. Expired token → redirect to login

## What We're NOT Doing

- Refresh tokens or silent token renewal
- Logout endpoint or explicit token revocation
- RBAC or multi-tenant auth changes
- Fixing deleted-user 401 asymmetry on ADR routes
- `localStorage` or cross-tab token sharing
- Reintroducing session cookies (including hybrid beacon cookie)
- CORS `allow_credentials` change (optional cleanup deferred — harmless with same-origin proxy)
- OpenAPI client generation or mobile SDK

## Implementation Approach

Backend-first transport swap in a thin vertical slice: change ingress (Bearer dependency + auth response schema), migrate tests, then frontend token lifecycle with client-only SSR and beacon redesign, finally deploy/env cleanup. Phases are independently verifiable with automated tests; manual browser checks gate frontend phases.

## Phase 1: Backend Bearer Transport

### Overview

Replace cookie read/write with Bearer header parsing and `AuthResponse` on register/login. Remove cookie settings from config.

### Changes Required:

#### 1. Auth schemas

**File**: `backend/infrastructure/api/schemas/auth.py`

**Intent**: Add a dedicated auth response type so `/me` stays token-free in OpenAPI while register/login expose `access_token`.

**Contract**: New `AuthResponse` model with field `access_token: str` only. Keep `UserResponse` unchanged for `/me`.

#### 2. Bearer dependency

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Read JWT from `Authorization: Bearer <token>` instead of session cookie; update structured log events.

**Contract**: `get_current_user_id` parses `request.headers.get("Authorization")` for `Bearer ` prefix; missing/malformed header logs `auth.missing_token` and raises 401; invalid JWT logs `auth.invalid_token`. Remove `SESSION_COOKIE_NAME` constant.

#### 3. Auth router

**File**: `backend/infrastructure/api/routers/auth.py`

**Intent**: Return `AuthResponse` with embedded token on register/login; stop setting cookies.

**Contract**: Register/login `response_model=AuthResponse`; remove `response: Response`, `settings: Settings`, `_set_session_cookie`, `SESSION_MAX_AGE_SECONDS`, and `SESSION_COOKIE_NAME` import. Return `AuthResponse(access_token=token)` directly. `/me` unchanged (`UserResponse`).

#### 4. Settings cleanup

**File**: `backend/infrastructure/config.py`

**Intent**: Remove cookie-only settings now that transport is Bearer-only.

**Contract**: Delete `cookie_secure`, `cookie_path`, and `parse_cookie_secure` validator.

### Success Criteria:

#### Automated Verification:

- Ruff check and format pass: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Type check passes: `cd backend && uv run ty check`
- App boots without `COOKIE_*` env vars (manual smoke: `Settings` only requires `jwt_secret`, `database_url`, `cors_origins`)

#### Manual Verification:

- OpenAPI `/docs` shows `AuthResponse` on POST `/auth/register` and `/auth/login`; `UserResponse` on GET `/auth/me` without token field
- Quick curl: register returns JSON with `access_token`, no `Set-Cookie` header

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Backend Test Migration

### Overview

Rewrite integration tests from cookie contract to Bearer contract; provide shared auth helpers for ADR tests.

### Changes Required:

#### 1. Auth test helpers and assertions

**File**: `backend/tests/infrastructure/api/test_auth.py`

**Intent**: Replace cookie helpers with Bearer helpers; delete cookie-flag tests; assert `access_token` in register/login bodies.

**Contract**: Replace `_me_with_session_cookie` → `_me_with_bearer(client, token)` setting `Authorization` header. Replace `_login_and_get_set_cookie` → `_login_and_get_token`. Delete tests asserting HttpOnly, SameSite, Max-Age, Secure, cookie path (~6 tests). Rename remaining tests from "cookie" to "token/bearer" wording. JWT rejection tests (tampered, expired, wrong secret, alg none, future nbf) use Bearer header. Assert no `Set-Cookie` on register/login.

#### 2. Shared auth fixture

**File**: `backend/tests/infrastructure/api/conftest.py`

**Intent**: Provide reusable Bearer auth for ADR integration tests.

**Contract**: Remove `cookie_secure`/`cookie_path` from `Settings` in `auth_client` fixture. Add helper e.g. `_register_and_get_token(client) -> str` or `auth_headers(token) -> dict` usable by ADR tests.

#### 3. ADR API tests

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: Replace implicit TestClient cookie jar with explicit Bearer headers.

**Contract**: After register/login, extract `access_token` from response JSON and pass `headers={"Authorization": f"Bearer {token}"}` on protected calls. Replace `auth_client.cookies.clear()` multi-user pattern with separate clients or explicit header overrides.

#### 4. Messaging test settings

**File**: `backend/tests/infrastructure/messaging/test_task_group_bus.py`

**Intent**: Remove obsolete cookie settings from inline `Settings` construction.

**Contract**: Drop `cookie_secure` and `cookie_path` kwargs from any `Settings(...)` call.

### Success Criteria:

#### Automated Verification:

- Auth integration tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_auth.py -v`
- ADR integration tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -v`
- Full backend suite passes: `cd backend && uv run pytest`

#### Manual Verification:

- Spot-check one tampered-token test and one multi-user ADR isolation test in test output

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Frontend Token Lifecycle

### Overview

Store `access_token` in `sessionStorage`, centralize authenticated `$fetch` in `useApi.ts`, update auth store to capture token on login/register and attach on `fetchUser`.

### Changes Required:

#### 1. Token storage module

**File**: `frontend/composables/useAuthToken.ts` (new)

**Intent**: Encapsulate sessionStorage read/write/clear for the access token with SSR-safe guards.

**Contract**: Export `getAccessToken()`, `setAccessToken(token: string)`, `clearAccessToken()`. All storage access guarded with `import.meta.client`. Key name e.g. `adr-flow.access_token`.

#### 2. Authenticated fetch wrapper

**File**: `frontend/composables/useApi.ts`

**Intent**: Attach `Authorization: Bearer` on protected calls; handle 401 globally.

**Contract**: Add `apiFetch<T>(url, options?)` that merges `Authorization` header when token present. On 401 response: call `clearAccessToken()`, clear auth store user (via store import or callback), `navigateTo('/login')` on client — skip redirect loop if already on `/login` or `/register`. Migrate all protected helpers (`createAdr`, `fetchAdr`, `updateAdr`, `searchAdrs`, `listAdrs`, `submitAdrForReview`, `retryAdrForReview`, `publishAdr`, `fetchAdrReviewStatus`) to use `apiFetch`. Keep `fetchHealth` on plain `$fetch`.

#### 3. Auth store

**File**: `frontend/app/stores/auth.ts`

**Intent**: Capture and persist token on login/register; use authenticated fetch for `/me`; expose token clear on auth failure.

**Contract**: Add `AuthResponse` type with `access_token`. On register/login success: `setAccessToken(response.access_token)`, then `fetchUser()` via `/auth/me` to hydrate user. Add `clearAuth()` clearing user + token (used by 401 handler). Export `clearAuth` if needed by `useApi`.

### Success Criteria:

#### Automated Verification:

- ESLint passes: `cd frontend && pnpm run lint`
- Typecheck passes: `cd frontend && pnpm run typecheck`
- Auth store tests pass: `cd frontend && pnpm exec vitest run tests/auth.store.test.ts`

#### Manual Verification:

- Dev login stores token in sessionStorage (DevTools → Application)
- Protected API call in Network tab shows `Authorization: Bearer` header

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Frontend SSR, Beacon Save & Tests

### Overview

Defer auth hydration to client-only; redesign unload-save for Bearer; update middleware and remaining frontend tests.

### Changes Required:

#### 1. Auth plugin — client-only

**File**: `frontend/app/plugins/auth.ts`

**Intent**: Avoid server-side `fetchUser` without a token.

**Contract**: Wrap body in `if (import.meta.client)` guard before calling `fetchUser()`.

#### 2. Auth middleware — client-only guard

**File**: `frontend/app/middleware/auth.ts`

**Intent**: Protected routes redirect to login only after client-side token check.

**Contract**: Return early on `import.meta.server` (allow SSR render); on client, call `fetchUser()` if no user, redirect to `/login` on failure.

#### 3. Guest middleware — client-only guard

**File**: `frontend/app/middleware/guest.ts`

**Intent**: Same SSR deferral for login/register redirect-when-authenticated.

**Contract**: Early return on server; client-only `fetchUser` + redirect to `/workspace` if authenticated.

#### 4. Index page redirect

**File**: `frontend/app/pages/index.vue`

**Intent**: Root redirect must not call authenticated API on SSR.

**Contract**: Move `fetchUser` + `navigateTo` into client-only path (e.g. `onMounted` or `if (import.meta.client)` block). SSR renders empty shell; client resolves redirect.

#### 5. Beacon save redesign

**File**: `frontend/app/composables/useAdrPersistence.ts`

**Intent**: Authenticate unload-save with Bearer header; drop cookie-dependent paths.

**Contract**: Replace `beaconSave` implementation: use `fetch(url, { method: 'POST', body: blob, keepalive: true, headers: { Authorization: Bearer ..., Content-Type: application/json } })` only — remove `sendBeacon` call and `credentials: 'include'`. Update `warnIfBeaconIsRisky` to reflect keepalive-only path (warn when payload > 60KB since keepalive has size limits). Read token via `getAccessToken()`; skip save if no token.

#### 6. Auth store tests

**File**: `frontend/tests/auth.store.test.ts`

**Intent**: Assert token persistence and Authorization header behavior.

**Contract**: Mock `sessionStorage`; assert `setAccessToken` on login/register; assert `Authorization` header in `$fetch`/`apiFetch` calls; update test names from "session cookie" to "Bearer token". Test `clearAuth` on 401 if testable at store level.

#### 7. Persistence tests (new)

**File**: `frontend/tests/useAdrPersistence.test.ts` (new)

**Intent**: Cover Bearer-authenticated unload save path.

**Contract**: Test that `beaconSave` (or renamed unload save) calls `fetch` with `keepalive: true` and `Authorization` header when token present; skips when no token.

### Success Criteria:

#### Automated Verification:

- Frontend tests pass: `cd frontend && pnpm run test`
- ESLint and typecheck pass

#### Manual Verification:

- Login → navigate to workspace → hard refresh → still authenticated (sessionStorage)
- Open new tab → not authenticated (sessionStorage is tab-scoped in some browsers — verify expected behavior: new tab has empty sessionStorage, must re-login)
- Edit ADR draft, switch tabs away (visibility hidden) → content saved
- Edit ADR, close tab → reopen ADR → unsaved work persisted if keepalive completed
- Manually expire token (DevTools: corrupt token) → next API call redirects to `/login`
- Register/login pages accessible without flash redirect on cold SSR load

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 5: Deploy & Docs Cleanup

### Overview

Remove obsolete cookie env vars from deployment surfaces and update documentation.

### Changes Required:

#### 1. Root env example

**File**: `.env.example`

**Intent**: Drop cookie vars from developer onboarding template.

**Contract**: Remove commented `COOKIE_SECURE` and `COOKIE_PATH` lines.

#### 2. Devcontainer env

**File**: `.devcontainer/devcontainer.json`

**Intent**: Stop injecting cookie settings into dev environment.

**Contract**: Remove `COOKIE_SECURE` and `COOKIE_PATH` from `remoteEnv`.

#### 3. GCP deploy scripts

**Files**: `deploy/gcp/run-api.flags`, `deploy/gcp/deploy-api.sh`

**Intent**: Production API deploy no longer sets cookie env vars.

**Contract**: Remove `COOKIE_SECURE=true,COOKIE_PATH=/api` from `--set-env-vars` in both files.

#### 4. Deploy documentation

**File**: `context/foundation/deploy-gcp.md`

**Intent**: Document Bearer-only auth in deployment guide.

**Contract**: Remove cookie env var references from env tables and example `--set-env-vars`; note auth is Bearer via Nitro same-origin proxy.

### Success Criteria:

#### Automated Verification:

- Pre-commit passes: `pre-commit run --all-files`
- Backend tests still pass: `cd backend && uv run pytest`
- Frontend tests still pass: `cd frontend && pnpm run test`

#### Manual Verification:

- Grep confirms no remaining `COOKIE_SECURE` / `COOKIE_PATH` / `cookie_secure` / `cookie_path` in production code paths (tests, config, deploy)
- README or deploy doc accurately describes JWT Bearer transport

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- `JwtTokenService` — unchanged, no modifications expected
- Auth store — token capture, header attachment, clear on failure
- `useAdrPersistence` — keepalive fetch with Bearer header

### Integration Tests:

- Auth API — register/login return `access_token`; Bearer on `/me`; JWT rejection matrix via header
- ADR API — all protected endpoints with Bearer; multi-user isolation via separate tokens
- Delete ~6 cookie-flag tests; retain behavioral coverage count via Bearer equivalents

### Manual Testing Steps:

1. Full register → workspace → create ADR → edit → blur save → tab close → reopen flow
2. Login after sessionStorage cleared (simulate expiry)
3. Verify no `session` cookie in Application tab after login
4. Verify 401 redirect from workspace when token removed
5. Cold-load protected URL while logged out → brief SSR shell then redirect to login

## Performance Considerations

- `fetch` + `keepalive` replaces `sendBeacon` — slightly lower unload reliability on hard browser kill; acceptable per plan decision. Payload warning at 60KB retained for keepalive limits.
- No additional network round-trips vs cookie model for normal API calls.
- Client-only SSR means protected pages render empty shell briefly before auth redirect — acceptable for MVP workspace app.

## Migration Notes

- **Big-bang transport swap** — no dual cookie+Bearer support period. Backend and frontend must ship together (full slice).
- Existing logged-in users lose session on deploy (cookie removed, no token in storage) — must re-login once.
- `JWT_SECRET` unchanged — existing tokens in flight remain valid until `exp` if somehow captured, but cookies won't be set post-deploy.

## References

- Research: `context/changes/jwt-bearer-access-token/research.md`
- Roadmap S-08: `context/foundation/roadmap.md`
- Original cookie auth: `context/archive/2026-06-14-account-access/plan.md`
- Beacon save design: `context/archive/2026-06-16-draft-authoring-persistence/plan.md`
- Backend dependency: `backend/infrastructure/api/dependencies.py:96-110`
- Auth router: `backend/infrastructure/api/routers/auth.py`
- Frontend auth store: `frontend/app/stores/auth.ts`
- Beacon blocker: `frontend/app/composables/useAdrPersistence.ts:25-41`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Backend Bearer Transport

#### Automated

- [x] 1.1 Ruff check and format pass: `cd backend && uv run ruff check . && uv run ruff format --check .` — 404ac34
- [x] 1.2 Type check passes: `cd backend && uv run ty check` — 404ac34
- [x] 1.3 App boots without `COOKIE_*` env vars — 404ac34

#### Manual

- [x] 1.4 OpenAPI shows `AuthResponse` on register/login; `UserResponse` on `/me` without token — 404ac34
- [x] 1.5 Register curl returns `access_token` in body, no `Set-Cookie` — 404ac34

### Phase 2: Backend Test Migration

#### Automated

- [x] 2.1 Auth integration tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_auth.py -v` — a729410
- [x] 2.2 ADR integration tests pass: `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py -v` — a729410
- [x] 2.3 Full backend suite passes: `cd backend && uv run pytest` — a729410

#### Manual

- [x] 2.4 Spot-check tampered-token and multi-user ADR isolation tests in output — a729410

### Phase 3: Frontend Token Lifecycle

#### Automated

- [x] 3.1 ESLint passes: `cd frontend && pnpm run lint` — c8967d3
- [x] 3.2 Typecheck passes: `cd frontend && pnpm run typecheck` — c8967d3
- [x] 3.3 Auth store tests pass: `cd frontend && pnpm exec vitest run tests/auth.store.test.ts` — c8967d3

#### Manual

- [x] 3.4 Dev login stores token in sessionStorage — c8967d3
- [x] 3.5 Protected API call shows `Authorization: Bearer` in Network tab — c8967d3

### Phase 4: Frontend SSR, Beacon Save & Tests

#### Automated

- [x] 4.1 Frontend tests pass: `cd frontend && pnpm run test`
- [x] 4.2 ESLint and typecheck pass

#### Manual

- [ ] 4.3 Hard refresh after login keeps user authenticated
- [ ] 4.4 Unload/visibility-hidden save persists draft with Bearer
- [ ] 4.5 Corrupt token redirects to `/login`
- [ ] 4.6 Cold SSR load of auth pages has no erroneous redirect flash

### Phase 5: Deploy & Docs Cleanup

#### Automated

- [ ] 5.1 Pre-commit passes: `pre-commit run --all-files`
- [ ] 5.2 Backend tests pass: `cd backend && uv run pytest`
- [ ] 5.3 Frontend tests pass: `cd frontend && pnpm run test`

#### Manual

- [ ] 5.4 Grep confirms no remaining cookie env/settings in production paths
- [ ] 5.5 Deploy docs describe Bearer-only auth
