# Account Access Implementation Plan

## Overview

Build the first full vertical slice: user registration, login, JWT-based sessions (httpOnly cookie), and route guards — across the FastAPI backend and Nuxt frontend. This slice also bootstraps the application architecture pattern (composition root, ports, event store adapter, projections) that all future slices depend on, and sets up the frontend UI stack (Tailwind CSS + shadcn-vue + Pinia).

## Current State Analysis

- **Backend:** F-02 delivered domain vocabulary (`User`, `UserRegistered`, value objects) and ORM models/migrations for `events`, `users`, `adrs` tables. No `application/` layer, no `bootstrap.py`, no API routers beyond `/health`, zero auth code or dependencies.
- **Frontend:** Minimal Nuxt 4 starter — one page, one composable (`useApi`), a Nitro `/api` proxy. No Tailwind, no shadcn, no Pinia, no auth pages or middleware.
- **Schema ready:** `users` table has `id`, `email` (unique), `password_hash`, `created_at`. `events` table ready for append-only writes.

### Key Discoveries:

- Email uniqueness enforced at DB level (`users_email_key`) — registration must catch `IntegrityError` and return generic error
- Nitro proxy at `frontend/server/routes/api/[...path].ts` forwards to backend — httpOnly cookies on same-origin work transparently
- Domain `PasswordHash` is a typed string wrapper — hashing logic belongs in infrastructure adapter
- `backend-application.mdc` rule: one file per use case, `{Name}Command` + `{Name}CommandHandler` class with DI via `__init__`
- Architecture rule: command handlers emit events → append to store → project. Routers never write projections directly.

## Desired End State

A user can visit `/register`, create an account with email + password (min 8 chars), and be automatically logged in with a 24h httpOnly JWT cookie. They land on `/workspace` (protected). Unauthenticated users hitting any protected route are redirected to `/login`. Authenticated users on `/login` or `/register` are redirected to `/workspace`. The backend exposes `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` — all following the hexagonal CQRS-lite architecture with proper event sourcing. The frontend uses Tailwind + shadcn-vue for styling, vee-validate + zod for forms, and Pinia for auth state.

### Verification:

- `POST /api/auth/register` → 201 + cookie set + `UserRegistered` event in DB
- `POST /api/auth/login` → 200 + cookie set
- `GET /api/auth/me` with cookie → 200 + user info
- `GET /api/auth/me` without cookie → 401
- Duplicate email registration → 400 generic error
- Frontend: `/workspace` redirects to `/login` when unauthenticated
- Frontend: `/login` redirects to `/workspace` when authenticated

## What We're NOT Doing

- Email verification (removed from MVP per PRD FR-002)
- Explicit logout endpoint (session expiry only per PRD)
- Password reset flow (conscious non-goal)
- Refresh tokens (single 24h JWT is the session)
- Login as a domain event (no aggregate mutation on login)
- RBAC / roles (flat permission model, single user type)
- Rate limiting on auth endpoints (post-MVP hardening)

## Implementation Approach

Build bottom-up backend-first: establish the composition root and port contracts, then implement the auth pipeline (register → event → projection → JWT cookie), then build the frontend UI stack and auth flow on top of the working API. This lets each phase be testable in isolation and avoids frontend work blocking on unfinished API contracts.

## Phase 1: Backend Foundation

### Overview

Add auth dependencies, create the `application/` layer skeleton with port Protocols, build `bootstrap.py` as the composition root, and wire `main.py` with lifespan, CORS, and session management.

### Changes Required:

#### 1. Dependencies

**File**: `backend/pyproject.toml`

**Intent**: Add runtime dependencies for password hashing and JWT token handling.

**Contract**: Add `argon2-cffi`, `PyJWT` to `[project.dependencies]`. Run `uv lock`.

#### 2. Application ports

**File**: `backend/application/__init__.py` (new package)

**Intent**: Create the application layer package.

**Contract**: Empty `__init__.py` files for `application/`, `application/ports/`, `application/commands/`, `application/queries/`.

**File**: `backend/application/ports/event_store.py`

**Intent**: Define the write-side contract for appending domain events to the event store.

**Contract**: `Protocol` class `EventStore` with `async def append(self, events: list, aggregate_id: UUID, aggregate_type: str) -> None`.

**File**: `backend/application/ports/user_projection.py`

**Intent**: Define the read/write contract for the users projection table.

**Contract**: `Protocol` class `UserProjection` with `async def insert(self, user_id, email, password_hash, created_at) -> None` and `async def find_by_email(self, email: str) -> UserReadModel | None` and `async def find_by_id(self, user_id: UUID) -> UserReadModel | None`. Include a `UserReadModel` dataclass (id, email, password_hash, created_at).

**File**: `backend/application/ports/password_hasher.py`

**Intent**: Abstract password hashing so it can be faked in tests.

**Contract**: `Protocol` class `PasswordHasher` with `def hash(self, password: str) -> str` and `def verify(self, password: str, hash: str) -> bool`.

**File**: `backend/application/ports/token_service.py`

**Intent**: Abstract JWT minting and validation.

**Contract**: `Protocol` class `TokenService` with `def create_token(self, user_id: UUID) -> str` and `def decode_token(self, token: str) -> UUID | None`.

#### 3. Infrastructure adapters

**File**: `backend/infrastructure/adapters/persistence/event_store.py`

**Intent**: Implement event append using SQLAlchemy async session.

**Contract**: Class `SqlEventStore` implementing `EventStore` protocol. Accepts `AsyncSession` (or session factory). Inserts rows into `events` table with `id=uuid4()`, serialized payload, `occurred_at`, `processed_at=None`.

**File**: `backend/infrastructure/adapters/persistence/projections/__init__.py` (new package)

**Intent**: Create projections sub-package.

**File**: `backend/infrastructure/adapters/persistence/projections/user_projection.py`

**Intent**: Implement user projection read/write using SQLAlchemy.

**Contract**: Class `SqlUserProjection` implementing `UserProjection` protocol. Insert maps to `INSERT INTO users`. Find methods query the `users` table. Returns `UserReadModel`.

**File**: `backend/infrastructure/adapters/auth/password_hasher.py`

**Intent**: Implement argon2 password hashing.

**Contract**: Class `Argon2PasswordHasher` implementing `PasswordHasher`. Uses `argon2-cffi`'s `PasswordHasher` internally.

**File**: `backend/infrastructure/adapters/auth/token_service.py`

**Intent**: Implement JWT minting/validation with httpOnly cookie configuration.

**Contract**: Class `JwtTokenService` implementing `TokenService`. Uses `PyJWT`. Token contains `sub` (user_id as string), `exp` (24h from now). Signs with a secret key from config. `decode_token` returns `UUID` on success, `None` on expired/invalid.

#### 4. Composition root

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Single place that wires all ports to adapters and constructs handler instances.

**Contract**: Function `create_app() -> FastAPI` or a `Bootstrap` class that:
- Creates async SQLAlchemy engine + `async_sessionmaker` from `DATABASE_URL`
- Instantiates adapters (event store, user projection, password hasher, token service)
- Instantiates command/query handlers with their dependencies
- Registers FastAPI routers
- Returns configured `FastAPI` app

#### 5. Main entry point update

**File**: `backend/main.py`

**Intent**: Replace bare app with bootstrapped application. Add lifespan for engine disposal and CORS middleware.

**Contract**: Import `create_app` from bootstrap, set CORS (allow frontend origin), keep `/health` route. Lifespan manages engine lifecycle.

### Success Criteria:

#### Automated Verification:

- Application starts without errors: `cd backend && uv run uvicorn main:app`
- Type check passes: `cd backend && uv run ty check`
- Lint passes: `cd backend && uv run ruff check .`
- Import graph: `application/` never imports from `infrastructure/` or `fastapi`
- `domain/` never imports from `application/` or `infrastructure/`

#### Manual Verification:

- `GET /health` still returns `{"status": "ok"}`
- Application logs show DB engine created on startup

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Backend Auth Pipeline

### Overview

Implement register and login use cases end-to-end: command handler emitting `UserRegistered` event, event store append + user projection insert in same transaction, JWT cookie on response. Expose auth routes.

### Changes Required:

#### 1. Register command

**File**: `backend/application/commands/register_user.py`

**Intent**: Handle user registration — validate email not taken, hash password, emit `UserRegistered`, persist event + projection.

**Contract**: `RegisterUserCommand` dataclass (email: str, password: str). `RegisterUserCommandHandler` with deps: `EventStore`, `UserProjection`, `PasswordHasher`. Returns `UUID` (new user_id). Raises domain-specific error if email taken (catch at router level).

#### 2. Auth query

**File**: `backend/application/queries/authenticate_user.py`

**Intent**: Verify credentials for login (not a command — login doesn't mutate state).

**Contract**: `AuthenticateUserQuery` dataclass (email: str, password: str). `AuthenticateUserQueryHandler` with deps: `UserProjection`, `PasswordHasher`. Returns `UUID` (user_id) on success, raises error on invalid credentials.

#### 3. Current user query

**File**: `backend/application/queries/get_current_user.py`

**Intent**: Fetch user profile by ID (for `GET /auth/me`).

**Contract**: `GetCurrentUserQuery` dataclass (user_id: UUID). `GetCurrentUserQueryHandler` with deps: `UserProjection`. Returns user read model or raises not-found.

#### 4. Auth router

**File**: `backend/infrastructure/api/routers/auth.py`

**Intent**: HTTP layer for registration, login, and current-user retrieval.

**Contract**:
- `POST /auth/register` — accepts `{email, password}`, calls `RegisterUserCommandHandler`, sets httpOnly cookie, returns 201 with user info.
- `POST /auth/login` — accepts `{email, password}`, calls `AuthenticateUserQueryHandler`, sets httpOnly cookie, returns 200 with user info.
- `GET /auth/me` — extracts user_id from cookie via `TokenService`, calls `GetCurrentUserQueryHandler`, returns 200 with user info.
- Cookie config: `httpOnly=True`, `secure=True` (configurable for dev), `samesite="lax"`, `path="/api"`, `max_age=86400`.

#### 5. API schemas

**File**: `backend/infrastructure/api/schemas/auth.py`

**Intent**: Pydantic request/response models for auth endpoints.

**Contract**: `RegisterRequest(email: str, password: str)`, `LoginRequest(email: str, password: str)`, `UserResponse(id: UUID, email: str, created_at: datetime)`. Password validation (min 8 chars) via Pydantic `field_validator`.

#### 6. Auth dependency

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: FastAPI `Depends` callable that extracts and validates the JWT cookie, returning the current user_id.

**Contract**: Function `get_current_user_id(request: Request) -> UUID` — reads cookie, decodes via `TokenService`, raises `HTTPException(401)` if missing/invalid/expired. Registered as a dependency that protected routes use.

#### 7. Domain error types

**File**: `backend/domain/errors.py`

**Intent**: Shared domain exceptions that command/query handlers raise and routers translate to HTTP status codes.

**Contract**: `EmailAlreadyTaken`, `InvalidCredentials`, `UserNotFound` — simple exception classes.

### Success Criteria:

#### Automated Verification:

- Type check passes: `cd backend && uv run ty check`
- Lint passes: `cd backend && uv run ruff check .`
- `POST /api/auth/register` with valid payload → 201 + `Set-Cookie` header
- `POST /api/auth/register` with duplicate email → 400 (generic message)
- `POST /api/auth/login` with correct creds → 200 + `Set-Cookie`
- `POST /api/auth/login` with wrong password → 401
- `GET /api/auth/me` with valid cookie → 200 + user JSON
- `GET /api/auth/me` without cookie → 401
- `events` table contains a `UserRegistered` row after registration
- `users` projection contains the new user row

#### Manual Verification:

- Test full flow via `curl` or HTTP client: register → login → me
- Verify cookie attributes in browser devtools (httpOnly, secure, path, max-age)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Frontend UI Stack

### Overview

Install and configure Tailwind CSS, shadcn-vue, Pinia, vee-validate, and zod in the Nuxt 4 app. Create base layouts for auth pages and the authenticated app shell.

### Changes Required:

#### 1. Tailwind CSS setup

**File**: `frontend/nuxt.config.ts`

**Intent**: Add `@nuxtjs/tailwindcss` module (or Tailwind v4 equivalent for Nuxt).

**Contract**: Register the Tailwind module in `modules` array. Create `frontend/tailwind.config.ts` with default content paths and shadcn-vue preset integration.

**File**: `frontend/app/assets/css/main.css`

**Intent**: Global CSS with Tailwind directives and shadcn CSS variables.

**Contract**: `@tailwind base; @tailwind components; @tailwind utilities;` plus CSS custom properties for shadcn theming (light/dark mode variables for `--background`, `--foreground`, `--primary`, etc.).

#### 2. shadcn-vue initialization

**File**: `frontend/components.json`

**Intent**: shadcn-vue configuration file specifying component paths and style.

**Contract**: Standard shadcn-vue `components.json` pointing to `app/components/ui/` for generated components, using "new-york" style and CSS variables.

**File**: `frontend/app/lib/utils.ts`

**Intent**: Utility functions required by shadcn-vue components (`cn` helper).

**Contract**: Export `cn(...inputs)` using `clsx` + `tailwind-merge`.

#### 3. Dependencies

**File**: `frontend/package.json`

**Intent**: Add UI stack dependencies.

**Contract**: Add `@nuxtjs/tailwindcss`, `tailwindcss`, `class-variance-authority`, `clsx`, `tailwind-merge`, `radix-vue`, `lucide-vue-next`, `@pinia/nuxt`, `pinia`, `vee-validate`, `@vee-validate/zod`, `zod`. Run `pnpm install`.

#### 4. Pinia module

**File**: `frontend/nuxt.config.ts`

**Intent**: Register Pinia module for state management.

**Contract**: Add `@pinia/nuxt` to `modules` array.

#### 5. Base shadcn components

**Intent**: Add the foundational shadcn-vue components needed for auth forms.

**Contract**: Generate via shadcn-vue CLI (or manually create): `Button`, `Input`, `Label`, `Card` (CardHeader, CardTitle, CardDescription, CardContent, CardFooter), `Form` (FormField, FormItem, FormLabel, FormControl, FormMessage). Files land in `frontend/app/components/ui/`.

#### 6. Layouts

**File**: `frontend/app/layouts/auth.vue`

**Intent**: Centered card layout for login/register pages — clean, minimal, branded.

**Contract**: Full-height flex container centering content vertically and horizontally. Slot for page content inside a constrained-width wrapper.

**File**: `frontend/app/layouts/default.vue`

**Intent**: App shell for authenticated pages — minimal header with app name and user context.

**Contract**: Top nav bar (app name, user email placeholder, no logout in MVP) + main content area with slot.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run build` completes without errors
- `cd frontend && pnpm run typecheck` passes
- `cd frontend && pnpm run lint` passes
- Tailwind classes render correctly (not purged) in dev server

#### Manual Verification:

- Visit `/` in browser — Tailwind styles applied, no FOUC
- shadcn components render with correct theming (CSS variables working)
- Both layouts render properly (auth centered, default with nav)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Frontend Auth Flow

### Overview

Build login/register pages with shadcn forms + vee-validate/zod validation, Pinia auth store, route middleware, and the protected `/workspace` landing page.

### Changes Required:

#### 1. Auth store

**File**: `frontend/app/stores/auth.ts`

**Intent**: Pinia store managing current user state and auth actions.

**Contract**: State: `user: { id, email, createdAt } | null`, `loading: boolean`. Actions: `register(email, password)`, `login(email, password)`, `fetchUser()` (calls `GET /api/auth/me`). Getters: `isAuthenticated`. On app init, call `fetchUser()` to hydrate from cookie.

#### 2. Auth composable

**File**: `frontend/app/composables/useAuth.ts`

**Intent**: Thin wrapper around the auth store for convenient use in pages/components.

**Contract**: Returns `{ user, isAuthenticated, login, register, fetchUser, loading }` from the Pinia store.

#### 3. Route middleware — auth guard

**File**: `frontend/app/middleware/auth.ts`

**Intent**: Redirect unauthenticated users to `/login`.

**Contract**: `defineNuxtRouteMiddleware` — if not authenticated (no user in store, and `fetchUser()` fails), redirect to `/login`.

#### 4. Route middleware — guest guard

**File**: `frontend/app/middleware/guest.ts`

**Intent**: Redirect authenticated users away from login/register.

**Contract**: `defineNuxtRouteMiddleware` — if authenticated, redirect to `/workspace`.

#### 5. Register page

**File**: `frontend/app/pages/register.vue`

**Intent**: Registration form with email + password + password confirmation, using shadcn Card + Form components.

**Contract**: Uses `definePageMeta({ layout: 'auth', middleware: ['guest'] })`. Form fields validated with zod schema (email format, password min 8, confirm match). On submit calls `auth.register()`. On success redirects to `/workspace`. On error shows generic toast/inline message. Link to `/login` for existing users.

#### 6. Login page

**File**: `frontend/app/pages/login.vue`

**Intent**: Login form with email + password, using shadcn Card + Form components.

**Contract**: Uses `definePageMeta({ layout: 'auth', middleware: ['guest'] })`. Form fields validated with zod (email format, password non-empty). On submit calls `auth.login()`. On success redirects to `/workspace`. On error shows "Invalid email or password" message. Link to `/register` for new users.

#### 7. Workspace landing page

**File**: `frontend/app/pages/workspace/index.vue`

**Intent**: Protected landing page — placeholder for future ADR list (S-02).

**Contract**: Uses `definePageMeta({ middleware: ['auth'] })`. Shows welcome message with user email. Placeholder content indicating this is where ADRs will appear.

#### 8. Root page update

**File**: `frontend/app/pages/index.vue`

**Intent**: Redirect root to either `/workspace` (if authenticated) or `/login`.

**Contract**: Simple redirect logic — if user is authenticated go to `/workspace`, otherwise go to `/login`.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run build` completes without errors
- `cd frontend && pnpm run typecheck` passes
- `cd frontend && pnpm run lint` passes
- Unit tests for auth store pass: `cd frontend && pnpm run test`

#### Manual Verification:

- Visit `/register` — form renders with shadcn styling, validates inputs
- Submit valid registration — lands on `/workspace` with user email shown
- Visit `/login` after clearing cookies — form renders
- Login with correct creds — lands on `/workspace`
- Login with wrong creds — error message shown, stays on `/login`
- Visit `/workspace` without cookie — redirected to `/login`
- Visit `/login` while authenticated — redirected to `/workspace`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 5: Backend Unit Tests

### Overview

Add unit tests for the auth pipeline: command handler, password hasher, JWT token service, and domain error handling. Uses fakes/mocks for ports (no real DB).

### Changes Required:

#### 1. Test fixtures and fakes

**File**: `backend/tests/unit/__init__.py` (new package)

**Intent**: Create unit test package.

**File**: `backend/tests/unit/fakes.py`

**Intent**: In-memory fake implementations of ports for unit testing.

**Contract**: `FakeEventStore` (appends to list), `FakeUserProjection` (in-memory dict), `FakePasswordHasher` (identity or simple prefix), `FakeTokenService` (returns predictable tokens).

#### 2. Register command handler tests

**File**: `backend/tests/unit/test_register_user.py`

**Intent**: Test registration logic: happy path, duplicate email, password hashing called.

**Contract**: Tests using fakes — verify `UserRegistered` event emitted with correct fields, user projection populated, password hash stored (not plain text). Verify `EmailAlreadyTaken` raised on duplicate.

#### 3. Authenticate user query tests

**File**: `backend/tests/unit/test_authenticate_user.py`

**Intent**: Test login logic: correct credentials return user_id, wrong password raises error, unknown email raises error.

**Contract**: Tests using fakes with pre-seeded user in `FakeUserProjection`.

#### 4. Token service tests

**File**: `backend/tests/unit/test_token_service.py`

**Intent**: Test JWT minting and validation with real `PyJWT` (no fake needed for this adapter).

**Contract**: Mint token → decode → get same user_id back. Expired token → returns None. Tampered token → returns None.

#### 5. Password hasher tests

**File**: `backend/tests/unit/test_password_hasher.py`

**Intent**: Test argon2 hashing: hash is not plaintext, verify matches, verify rejects wrong password.

**Contract**: Uses real `Argon2PasswordHasher` — integration-ish but fast and deterministic.

### Success Criteria:

#### Automated Verification:

- All tests pass: `cd backend && uv run pytest tests/unit/ -v`
- Type check passes: `cd backend && uv run ty check`
- Lint passes: `cd backend && uv run ruff check .`
- Coverage: register handler, authenticate handler, token service, password hasher all covered

#### Manual Verification:

- Review test output for clarity — test names describe behavior

**Implementation Note**: After completing this phase and all automated verification passes, the slice is complete.

---

## Testing Strategy

### Unit Tests:

- `RegisterUserCommandHandler` — happy path, duplicate email, password hashing
- `AuthenticateUserQueryHandler` — valid creds, invalid password, unknown email
- `JwtTokenService` — mint, decode, expired, tampered
- `Argon2PasswordHasher` — hash, verify correct, verify incorrect
- Frontend auth store — register/login actions (mocked fetch)

### Manual Testing Steps:

1. Start both servers (`just dev`)
2. Navigate to `/register` — verify form renders with Tailwind/shadcn styling
3. Register with a new email — verify redirect to `/workspace`, cookie set
4. Open devtools → Application → Cookies — verify httpOnly, 24h expiry
5. Refresh page — verify still authenticated (cookie persists)
6. Clear cookies → refresh — verify redirect to `/login`
7. Login with registered credentials — verify redirect to `/workspace`
8. Try registering with same email — verify generic error shown
9. Try logging in with wrong password — verify error message

## Performance Considerations

- Argon2 hashing is intentionally slow (~200ms) — acceptable for auth endpoints, not for hot paths
- JWT validation is fast (symmetric HMAC) — no DB call on every protected request
- User projection lookup by email uses the unique index — single-row B-tree scan

## Migration Notes

No new migrations needed — F-02 already created the `events` and `users` tables with the correct schema. S-01 only writes to existing tables through the new application layer.

## References

- Architecture: `context/foundation/application-architecture.md`
- Tech stack: `context/foundation/tech-stack.md`
- PRD auth sections: US-03, FR-001, FR-003, Access Control
- Backend conventions: `.cursor/rules/backend-architecture.mdc`, `.cursor/rules/backend-application.mdc`
- F-02 plan: `context/changes/persistence-scaffold/plan.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend Foundation

#### Automated

- [ ] 1.1 Application starts without errors
- [ ] 1.2 Type check passes
- [ ] 1.3 Lint passes
- [ ] 1.4 Import graph: application/ never imports infrastructure/
- [ ] 1.5 Import graph: domain/ never imports application/ or infrastructure/

#### Manual

- [ ] 1.6 GET /health returns {"status": "ok"}
- [ ] 1.7 Application logs show DB engine created on startup

### Phase 2: Backend Auth Pipeline

#### Automated

- [ ] 2.1 Type check passes
- [ ] 2.2 Lint passes
- [ ] 2.3 POST /api/auth/register → 201 + Set-Cookie
- [ ] 2.4 POST /api/auth/register duplicate → 400
- [ ] 2.5 POST /api/auth/login correct creds → 200 + Set-Cookie
- [ ] 2.6 POST /api/auth/login wrong password → 401
- [ ] 2.7 GET /api/auth/me with cookie → 200
- [ ] 2.8 GET /api/auth/me without cookie → 401
- [ ] 2.9 events table has UserRegistered row
- [ ] 2.10 users projection has new user row

#### Manual

- [ ] 2.11 Full curl flow: register → login → me
- [ ] 2.12 Verify cookie attributes in browser devtools

### Phase 3: Frontend UI Stack

#### Automated

- [ ] 3.1 pnpm run build completes
- [ ] 3.2 pnpm run typecheck passes
- [ ] 3.3 pnpm run lint passes
- [ ] 3.4 Tailwind classes render (not purged)

#### Manual

- [ ] 3.5 Tailwind styles applied, no FOUC
- [ ] 3.6 shadcn components render with correct theming
- [ ] 3.7 Both layouts render properly

### Phase 4: Frontend Auth Flow

#### Automated

- [ ] 4.1 pnpm run build completes
- [ ] 4.2 pnpm run typecheck passes
- [ ] 4.3 pnpm run lint passes
- [ ] 4.4 Auth store unit tests pass

#### Manual

- [ ] 4.5 Register form renders and validates
- [ ] 4.6 Successful registration lands on /workspace
- [ ] 4.7 Login form renders
- [ ] 4.8 Login with correct creds → /workspace
- [ ] 4.9 Login with wrong creds → error shown
- [ ] 4.10 /workspace without cookie → redirected to /login
- [ ] 4.11 /login while authenticated → redirected to /workspace

### Phase 5: Backend Unit Tests

#### Automated

- [ ] 5.1 All unit tests pass
- [ ] 5.2 Type check passes
- [ ] 5.3 Lint passes
- [ ] 5.4 Coverage: all handlers and services tested
