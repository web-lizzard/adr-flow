# Account Access — Plan Brief

> Full plan: `context/changes/account-access/plan.md`

## What & Why

Build user registration, login, and JWT-based sessions so every future slice has a per-user isolation boundary. This is the first vertical slice that wires the hexagonal CQRS-lite architecture end-to-end (domain → application → infrastructure → frontend), establishing patterns all subsequent work follows.

## Starting Point

F-02 delivered the `events`, `users`, and `adrs` Postgres tables plus domain vocabulary (`User`, `UserRegistered`, value objects). The backend is a bare `/health` endpoint with no application layer. The frontend is a minimal Nuxt 4 starter with no styling framework, no auth, and no state management.

## Desired End State

A user can register with email + password, be auto-logged-in with a 24h httpOnly JWT cookie, and land on a protected `/workspace` page. Unauthenticated visitors are redirected to `/login`. The frontend uses Tailwind CSS + shadcn-vue for a clean, modern UI with vee-validate + zod for form handling.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Token storage | httpOnly cookie | Same-origin Nitro proxy forwards cookies transparently; no client-side token management needed. |
| Token lifetime | 24 hours | Covers a full work session without re-login friction; no refresh token complexity in MVP. |
| Password hashing | argon2 (argon2-cffi) | Modern PHC winner, memory-hard — strongest option available. |
| Post-register UX | Auto-login (cookie set on register) | Eliminates unnecessary friction; user lands directly in workspace. |
| Duplicate email error | Generic message ("Unable to create account") | Prevents email enumeration attacks. |
| Password policy | Minimum 8 characters, no complexity rules | Simple for MVP; avoid false security of complexity rules. |
| Port abstractions | Protocols introduced now | Enables test fakes and sets clean pattern for all future slices. |
| Dependency injection | Manual composition root (bootstrap.py) + FastAPI Depends | Explicit wiring, no framework magic, easy to reason about. |
| Form validation | vee-validate + zod | Declarative, pairs well with shadcn form components. |
| Protected route | /workspace | Matches PRD's "per-user ADR workspace" concept. |
| Testing approach | Unit tests (fakes for ports, no real DB) | Fast, focused on business logic correctness. |

## Scope

**In scope:**
- Backend: composition root, ports (EventStore, UserProjection, PasswordHasher, TokenService), register command, login/me queries, auth router, JWT cookie handling
- Frontend: Tailwind + shadcn-vue + Pinia setup, login/register pages, auth middleware, /workspace placeholder
- Unit tests for auth pipeline

**Out of scope:**
- Email verification, password reset, explicit logout, refresh tokens, rate limiting, RBAC, login events

## Architecture / Approach

Backend follows hexagonal CQRS-lite: `POST /auth/register` → router → `RegisterUserCommandHandler` → emit `UserRegistered` → append to `events` table + insert into `users` projection (same transaction) → set JWT cookie. Login is a query (no state mutation). Frontend stores user state in Pinia, hydrated on app init via `GET /auth/me`; route middleware redirects based on auth status.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend Foundation | Composition root, ports, session management, lifespan | Over-engineering the bootstrap for MVP scope |
| 2. Backend Auth Pipeline | Register/login/me endpoints, JWT cookies, event persistence | Transaction boundaries between event append and projection |
| 3. Frontend UI Stack | Tailwind + shadcn-vue + Pinia wired into Nuxt 4 | shadcn-vue compatibility with Nuxt 4 / Vue 3.5 |
| 4. Frontend Auth Flow | Login/register pages, middleware, /workspace | Cookie handling through Nitro proxy in SSR context |
| 5. Backend Unit Tests | Fakes + tests for handlers and services | Fakes drifting from real adapter behavior |

**Prerequisites:** F-02 persistence scaffold complete (tables migrated, domain vocabulary in place).
**Estimated effort:** ~3-4 sessions across 5 phases.

## Open Risks & Assumptions

- httpOnly cookie through Nitro SSR proxy — need to verify cookie forwarding in both SSR and client-side navigation contexts
- shadcn-vue + Nuxt 4 compatibility — relatively new combination; may need manual component adjustments
- No integration tests in this slice — relying on unit tests + manual verification; integration tests can be added as a follow-up

## Success Criteria (Summary)

- User can register, login, and reach `/workspace` end-to-end through the browser
- Unauthenticated access to protected routes redirects to `/login`
- `UserRegistered` event correctly persisted in the events table on registration
