# JWT Bearer Access Token — Plan Brief

> Full plan: `context/changes/jwt-bearer-access-token/plan.md`
> Research: `context/changes/jwt-bearer-access-token/research.md`

## What & Why

ADR Flow already mints HS256 JWTs on register/login but stores them in an httponly session cookie. S-08 switches transport to return `access_token` in the response body and accept `Authorization: Bearer` on protected routes — enabling explicit client token management and natural API client usage, without changing registration, login, or 24h expiry semantics.

## Starting Point

Backend: `JwtTokenService` is transport-agnostic; `get_current_user_id` reads `session` cookie; register/login call `_set_session_cookie`. Frontend: auth store holds in-memory user only; all `$fetch` calls omit headers; unload save uses `sendBeacon` (no custom headers) with cookie fallback. Eleven protected endpoints funnel through one dependency.

## Desired End State

Users log in, receive `access_token` in JSON, and the frontend stores it in `sessionStorage` and attaches it on every protected call. No session cookie. Expired/invalid tokens redirect to login. Unload draft save works via `fetch` + `keepalive` + Bearer. Deploy scripts no longer reference `COOKIE_*` env vars.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Token storage | `sessionStorage` | Tab-scoped, survives refresh within tab; lower XSS persistence window than `localStorage` | Plan |
| SSR auth | Client-only hydration | Avoids server-side Bearer forwarding complexity; plugin/middleware defer to client | Plan |
| Unload save | `fetch` + `keepalive` + Bearer | Only path that supports custom headers without reintroducing cookies | Plan |
| Response shape | Separate `AuthResponse` | Keeps `/me` OpenAPI clean; token only on register/login | Plan |
| 401 handling | Clear state + redirect to `/login` | Explicit UX when session expires; matches workspace guard pattern | Plan |
| Delivery scope | Full slice | Backend + frontend + tests + deploy/docs in one change | Plan |
| Deleted-user on ADR routes | Keep asymmetry | `/me` already 401s; ADR routes unchanged — out of scope | Research |
| Refresh / logout | None | Roadmap parked; 24h JWT `exp`, users re-login | Research |

## Scope

**In scope:**

- Bearer parsing in `get_current_user_id`
- `AuthResponse` on register/login; remove cookie helper
- Remove `COOKIE_*` from config, deploy, devcontainer, docs
- Backend test migration (~30 auth tests, ADR fixtures)
- Frontend `sessionStorage`, `apiFetch`, auth store, 401 redirect
- Client-only SSR (plugin, middleware, index page)
- `useAdrPersistence` keepalive + Bearer
- Frontend auth + persistence tests

**Out of scope:**

- Refresh tokens, logout endpoint, RBAC
- Hybrid cookie for beacon
- CORS `allow_credentials` change
- Fixing deleted-user JWT acceptance on ADR routes

## Architecture / Approach

Transport-only migration: swap HTTP ingress (cookie → Bearer header) and egress (Set-Cookie → JSON body). Domain, commands, queries, and `JwtTokenService` unchanged. Frontend adds token lifecycle layer (`useAuthToken` + `apiFetch`) consumed by auth store and all ADR API helpers. Nitro proxy unchanged — forwards `Authorization` transparently.

```
Login/Register → API returns AuthResponse { user + access_token }
              → frontend setAccessToken(sessionStorage)
Protected call → apiFetch adds Authorization: Bearer
              → get_current_user_id decodes JWT → user_id
401           → clearAuth() → navigateTo(/login)
Unload save   → fetch(keepalive) + Bearer (no sendBeacon)
```

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Backend Bearer transport | Bearer dependency, AuthResponse, config cleanup | Breaking API contract for existing cookie clients |
| 2. Backend test migration | Bearer fixtures, delete cookie-flag tests | Large test rewrite surface |
| 3. Frontend token lifecycle | sessionStorage, apiFetch, auth store | 401 redirect loops if not guarded |
| 4. Frontend SSR & beacon | Client-only hydration, keepalive save, tests | Unload save less reliable than sendBeacon |
| 5. Deploy & docs cleanup | Remove COOKIE_* everywhere | Missed env reference breaks deploy |

**Prerequisites:** S-01 (account-access) complete; `JWT_SECRET` configured
**Estimated effort:** ~2-3 focused sessions across 5 phases

## Open Risks & Assumptions

- Big-bang deploy: all logged-in users must re-login once (cookie removed, no token in storage)
- `fetch` + `keepalive` may lose saves on hard browser kill — acceptable tradeoff vs cookie beacon
- Client-only SSR: brief empty shell before auth redirect on protected routes
- XSS becomes higher impact (token in JS-accessible storage vs httpOnly cookie)

## Success Criteria (Summary)

- Register/login return `access_token`; no session cookie; Bearer works on all 11 protected routes
- Browser login → refresh → workspace loads; corrupt token → redirect to login
- Unload/blur save persists draft edits with Bearer auth
- No `COOKIE_*` references remain in config or deploy
