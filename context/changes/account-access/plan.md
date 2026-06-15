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

**Contract**: Add `argon2-cffi`, `PyJWT`, `pydantic`, `pydantic-settings` to `[project.dependencies]`. Run `uv lock`.

**Note**: Domain events are Pydantic models (`domain/events.py` base + per-aggregate events) for JSON serialization in the event store. Runtime config uses `pydantic-settings` (`infrastructure/config.py`).

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

**Phase 1 interim note**: `SqlEventStore.append()` and `SqlUserProjection.insert()` each open their own session and commit independently. That is acceptable for Phase 1 (no multi-step writes yet). Phase 2 refactors write paths behind `UnitOfWork` so register is atomic.

### Overview

Implement register and login use cases end-to-end: command handler emitting `UserRegistered` event, event store append + user projection insert in same transaction, JWT cookie on response. Expose auth routes.

**Transaction model:** Command handlers must not import SQLAlchemy or manage `AsyncSession` / `commit()` directly. Phase 2 introduces a `UnitOfWork` port (and `SqlUnitOfWork` adapter) that owns the write-side transaction boundary. `RegisterUserCommandHandler` opens a unit of work, performs event append + projection insert through session-scoped ports, and relies on the adapter to commit or roll back. Phase 1 persistence adapters self-commit per call as an interim convenience; Phase 2 refactors write paths to run inside a shared unit of work (read paths keep short-lived sessions).

### Changes Required:

#### 1. Unit of work port

**File**: `backend/application/ports/unit_of_work.py`

**Intent**: Define the write-side transaction boundary so command handlers coordinate multi-step persistence without knowing about the database driver, sessions, or commit semantics.

**Contract**:

- `UnitOfWork` `Protocol` exposing:
  - `event_store: EventStore` — store bound to the current transaction
  - `user_projection: UserProjection` — projection bound to the current transaction
  - `async def commit() -> None`
  - `async def rollback() -> None`
- `UnitOfWorkFactory` `Protocol` with `begin()` returning an async context manager that yields a `UnitOfWork`. On clean exit the adapter commits; on exception it rolls back.

Command handlers depend on `UnitOfWorkFactory`, not on `AsyncSession`.

#### 2. Unit of work adapter and persistence refactor

**File**: `backend/infrastructure/adapters/persistence/unit_of_work.py`

**Intent**: Implement the transaction boundary with SQLAlchemy + asyncpg.

**Contract**: `SqlUnitOfWorkFactory` accepts `async_sessionmaker`. `begin()` opens one `AsyncSession`, starts one transaction (`session.begin()`), constructs session-scoped `SqlEventStore` and `SqlUserProjection` instances sharing that session, yields `SqlUnitOfWork`, and commits or rolls back on context exit.

**File**: `backend/infrastructure/adapters/persistence/event_store.py` (modify)

**Intent**: Stop self-committing when participating in a unit of work.

**Contract**: `SqlEventStore` accepts an optional `AsyncSession` at construction. When constructed with a session (from `SqlUnitOfWork`), `append()` only adds rows — no `session_factory()` / `session.begin()`. When constructed with only a session factory (Phase 1 standalone use), retain current self-contained behavior for backward compatibility until all write paths use UoW.

**File**: `backend/infrastructure/adapters/persistence/projections/user_projection.py` (modify)

**Intent**: Same session-scoped write behavior as the event store.

**Contract**: `SqlUserProjection.insert()` follows the same session-injection rule as `SqlEventStore.append()`. Read methods (`find_by_email`, `find_by_id`) continue to open their own short-lived sessions — queries do not need a unit of work.

#### 3. Register command

**File**: `backend/application/commands/register_user.py`

**Intent**: Handle user registration — validate email not taken, hash password, emit `UserRegistered`, persist event + projection atomically.

**Contract**: `RegisterUserCommand` dataclass (email: str, password: str). `RegisterUserCommandHandler` with deps: `UnitOfWorkFactory`, `PasswordHasher`. `handle()` uses `async with uow_factory.begin() as uow:` then checks `uow.user_projection.find_by_email`, hashes password, appends `UserRegistered` via `uow.event_store`, inserts via `uow.user_projection`. Returns `UUID` (new user_id). Raises `EmailAlreadyTaken` if email taken. Handler never calls `commit()` directly — the unit-of-work adapter owns that.

#### 4. Auth query

**File**: `backend/application/queries/authenticate_user.py`

**Intent**: Verify credentials for login (not a command — login doesn't mutate state).

**Contract**: `AuthenticateUserQuery` dataclass (email: str, password: str). `AuthenticateUserQueryHandler` with deps: `UserProjection`, `PasswordHasher`. Returns `UUID` (user_id) on success, raises error on invalid credentials.

#### 5. Current user query

**File**: `backend/application/queries/get_current_user.py`

**Intent**: Fetch user profile by ID (for `GET /api/auth/me`).

**Contract**: `GetCurrentUserQuery` dataclass (user_id: UUID). `GetCurrentUserQueryHandler` with deps: `UserProjection`. Returns user read model or raises not-found.

#### 6. Auth router

**File**: `backend/infrastructure/api/routers/auth.py`

**Intent**: HTTP layer for registration, login, and current-user retrieval.

**Contract**:
- `POST /api/auth/register` — accepts `{email, password}`, calls `RegisterUserCommandHandler`, sets httpOnly cookie, returns 201 with user info.
- `POST /api/auth/login` — accepts `{email, password}`, calls `AuthenticateUserQueryHandler`, sets httpOnly cookie, returns 200 with user info.
- `GET /api/auth/me` — extracts user_id from cookie via `TokenService`, calls `GetCurrentUserQueryHandler`, returns 200 with user info.
- Cookie config: `httpOnly=True`, `secure=True` (configurable for dev), `samesite="lax"`, `path="/api"`, `max_age=86400`.

#### 7. API schemas

**File**: `backend/infrastructure/api/schemas/auth.py`

**Intent**: Pydantic request/response models for auth endpoints.

**Contract**: `RegisterRequest(email: str, password: str)`, `LoginRequest(email: str, password: str)`, `UserResponse(id: UUID, email: str, created_at: datetime)`. Password validation (min 8 chars) via Pydantic `field_validator`.

#### 8. Auth dependency

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: FastAPI `Depends` callable that extracts and validates the JWT cookie, returning the current user_id.

**Contract**: Function `get_current_user_id(request: Request) -> UUID` — reads cookie, decodes via `TokenService`, raises `HTTPException(401)` if missing/invalid/expired. Registered as a dependency that protected routes use.

#### 9. Domain error types

**File**: `backend/domain/errors.py`

**Intent**: Shared domain exceptions that command/query handlers raise and routers translate to HTTP status codes.

**Contract**: `EmailAlreadyTaken`, `InvalidCredentials`, `UserNotFound` — simple exception classes.

#### 10. Bootstrap wiring

**File**: `backend/infrastructure/bootstrap.py` (modify)

**Intent**: Wire `SqlUnitOfWorkFactory` and inject it into `RegisterUserCommandHandler`. Query handlers continue to receive standalone `SqlUserProjection` (read-only, no UoW).

**Contract**: Bootstrap constructs `SqlUnitOfWorkFactory(session_factory)`, registers auth router, and exposes `UnitOfWorkFactory` to the register handler. Standalone `event_store` / `user_projection` on `app.state` may remain for health/debug or be removed if unused — register must go through UoW only.

### Phase 2 implementation addendum — read/write projection split

During implementation, read access was split from `UserProjection` into a dedicated
`UserRepository` port and SQL adapter. `UserProjection` is now the write-side
projection port used by the unit of work; `UserRepository` is the read-side port used
by auth queries and the duplicate-email pre-check.

This keeps command writes coordinated by `UnitOfWork` while preserving short-lived
read sessions for query handlers. The accepted drift from the original contract is:

- `UserProjection` exposes `insert()` only.
- `UserRepository` owns `find_by_email()` and `find_by_id()`.
- `RegisterUserCommandHandler`, `AuthenticateUserQueryHandler`, and
  `GetCurrentUserQueryHandler` depend on `UserRepository` for reads.

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
- Failed registration (e.g. duplicate email) leaves no orphan row in `events` or `users` — unit of work rolled back

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

**Contract**: `FakeUnitOfWork` / `FakeUnitOfWorkFactory` (coordinates fake event store + projection in one logical transaction; commit/rollback semantics for tests), `FakeEventStore` (appends to list), `FakeUserProjection` (in-memory dict), `FakePasswordHasher` (identity or simple prefix), `FakeTokenService` (returns predictable tokens).

#### 2. Register command handler tests

**File**: `backend/tests/unit/test_register_user.py`

**Intent**: Test registration logic: happy path, duplicate email, password hashing called.

**Contract**: Tests using `FakeUnitOfWorkFactory` — verify `UserRegistered` event emitted with correct fields, user projection populated, password hash stored (not plain text). Verify `EmailAlreadyTaken` raised on duplicate and no partial writes remain after failure.

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

- [x] 1.1 Application starts without errors — 6fc32bb
- [x] 1.2 Type check passes — 6fc32bb
- [x] 1.3 Lint passes — 6fc32bb
- [x] 1.4 Import graph: application/ never imports infrastructure/ — 6fc32bb
- [x] 1.5 Import graph: domain/ never imports application/ or infrastructure/ — 6fc32bb

#### Manual

- [x] 1.6 GET /health returns {"status": "ok"} — 6fc32bb
- [x] 1.7 Application logs show DB engine created on startup — 6fc32bb

### Phase 2: Backend Auth Pipeline

#### Automated

- [x] 2.1 Type check passes — 272f1ae
- [x] 2.2 Lint passes — 272f1ae
- [x] 2.3 POST /api/auth/register → 201 + Set-Cookie — 272f1ae
- [x] 2.4 POST /api/auth/register duplicate → 400 — 272f1ae
- [x] 2.5 POST /api/auth/login correct creds → 200 + Set-Cookie — 272f1ae
- [x] 2.6 POST /api/auth/login wrong password → 401 — 272f1ae
- [x] 2.7 GET /api/auth/me with cookie → 200 — 272f1ae
- [x] 2.8 GET /api/auth/me without cookie → 401 — 272f1ae
- [x] 2.9 events table has UserRegistered row — 272f1ae
- [x] 2.10 users projection has new user row — 272f1ae
- [x] 2.11 Failed register leaves no orphan event or user row — 272f1ae

#### Manual

- [ ] 2.12 Full curl flow: register → login → me
- [ ] 2.13 Verify cookie attributes in browser devtools

### Phase 3: Frontend UI Stack

#### Automated

- [x] 3.1 pnpm run build completes — c429a29
- [x] 3.2 pnpm run typecheck passes — c429a29
- [x] 3.3 pnpm run lint passes — c429a29
- [x] 3.4 Tailwind classes render (not purged) — c429a29

#### Manual

- [x] 3.5 Tailwind styles applied, no FOUC — c429a29
- [x] 3.6 shadcn components render with correct theming — c429a29
- [x] 3.7 Both layouts render properly — c429a29

### Phase 4: Frontend Auth Flow

#### Automated

- [x] 4.1 pnpm run build completes
- [x] 4.2 pnpm run typecheck passes
- [x] 4.3 pnpm run lint passes
- [x] 4.4 Auth store unit tests pass

#### Manual

- [x] 4.5 Register form renders and validates
- [x] 4.6 Successful registration lands on /workspace
- [x] 4.7 Login form renders
- [x] 4.8 Login with correct creds → /workspace
- [x] 4.9 Login with wrong creds → error shown
- [x] 4.10 /workspace without cookie → redirected to /login
- [x] 4.11 /login while authenticated → redirected to /workspace

### Phase 5: Backend Unit Tests

#### Automated

- [ ] 5.1 All unit tests pass
- [ ] 5.2 Type check passes
- [ ] 5.3 Lint passes
- [ ] 5.4 Coverage: all handlers and services tested
