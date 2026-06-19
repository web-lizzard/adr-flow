<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Persistence Scaffold — Phase 3

- **Plan**: context/changes/persistence-scaffold/plan.md
- **Scope**: Phase 3 of 4 (Schema Models, Initial Migration, and Local Verification)
- **Date**: 2026-06-14
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Executive summary

Phase 3 delivers what the plan asked for: `models.py` with `events`/`users`/`adrs`, an initial Alembic revision with PG15-compatible JSONB and the required indexes, persistence tests, and `backend/README.md` migration docs. With a working `DATABASE_URL` (`postgresql://postgres:postgres@postgres:5432/adr_flow` in this workspace), all automated checks pass — including `alembic check` (no metadata drift).

The main gap was **operational**: default devcontainer `DATABASE_URL` (`dev:dev@postgres:5432/app`) failed auth against the initialized Postgres volume. **F1 resolved** — compose and `remoteEnv` now use `postgres:postgres@postgres:5432/adr_flow`. Progress checkboxes 3.1–3.7 are marked done without commit SHAs; manual items 3.8–3.10 remain unchecked (schema inspection below provides partial evidence).

## Automated verification (re-run 2026-06-14)

| Check | Command | Result |
|-------|---------|--------|
| 3.1 Fresh migrate | `just migrate-backend` | PASS with `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/adr_flow`; FAIL with default `dev:dev@postgres:5432/app` (auth error) |
| 3.2 Idempotent migrate | `just migrate-backend` (×2) | PASS (with working URL) |
| 3.3 Head check | `cd backend && uv run alembic current --check-heads` | PASS → `001_initial (head)` |
| 3.3b Drift guard | `cd backend && uv run alembic check` | PASS — "No new upgrade operations detected." |
| 3.4 Persistence tests | `cd backend && uv run pytest tests/infrastructure/adapters/persistence` | PASS 8/8 (with working URL); 4 errors with default URL |
| 3.5 Full backend tests | `just test-backend` | PASS 16/16 (with working URL); 4 errors with default URL |
| 3.6 Lint | `cd backend && uv run ruff check .` | PASS |
| 3.7 Types | `cd backend && uv run ty check` | PASS |

## Manual verification evidence (partial — items still unchecked in plan)

Schema inspected after `alembic upgrade head` on `adr_flow` database:

| Table | Columns | Notes |
|-------|---------|-------|
| `events` | id, aggregate_type, aggregate_id, event_type, payload, occurred_at, processed_at | Indexes: `ix_events_aggregate`, `ix_events_processed_at` |
| `users` | id, email, password_hash, created_at | Unique constraint on `email` (`users_email_key`) |
| `adrs` | id, user_id, title, content, status, review_annotations, is_deleted, created_at, updated_at, reviewed_at | `review_annotations` JSONB nullable; `is_deleted` BOOLEAN NOT NULL; index `ix_adrs_user_id` |

## Plan drift summary

| Planned item | Verdict |
|--------------|---------|
| `models.py` — three tables, no repos | MATCH |
| Initial migration `001_initial_events_users_adrs.py` | MATCH |
| Persistence tests under `tests/infrastructure/adapters/persistence/` | MATCH |
| `backend/README.md` — URL, just recipes, migration vs runtime | MATCH |
| `database_url.py` (URL normalization helper) | EXTRA — aligns with plan Critical Implementation Details; used by `env.py` and tests |

## Findings

### F1 — Default DATABASE_URL breaks migrate and test-backend

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: `.devcontainer/devcontainer.json:24`, `backend/README.md:18-19`, `backend/tests/infrastructure/adapters/persistence/conftest.py:37-45`
- **Detail**: Devcontainer `remoteEnv` sets `DATABASE_URL=postgresql://dev:dev@postgres:5432/app` (matches `docker-compose.yml` defaults). In this workspace the Postgres volume was initialized with different credentials (`postgres:postgres`, database `adr_flow` per root `.env`). `just migrate-backend` and migration integration tests fail with `password authentication failed for user "dev"`. README documents the compose-default URL, not how to detect/fix a stale volume.
- **Fix A ⭐ Recommended**: Align credentials — either recreate the Postgres volume so `dev:dev@app` works, or update `devcontainer.json` / `.env.example` to document the override pattern and ensure `just test-backend` sources `.env` when present.
  - Strength: Restores out-of-box `just migrate-backend` / `just test-backend` for all developers.
  - Tradeoff: Volume recreation loses local data; documenting override leaves burden on each dev with stale volumes.
  - Confidence: HIGH — failure reproduced with default env; passes with corrected URL.
  - Blind spot: Other devcontainer setups may already have fresh `dev:dev` volumes.
- **Fix B**: Change `conftest.py` to `pytest.skip` when Postgres is unreachable (not only when URL unset).
  - Strength: `just test-backend` passes without Postgres for local host-side runs.
  - Tradeoff: Masks misconfiguration; CI must still fail when DB is required (plan-review already flagged this tension).
  - Confidence: MEDIUM — conflicts with plan intent to fail clearly when DB is expected.
  - Blind spot: Phase 4 CI will set URL explicitly; skip behavior may hide local setup bugs.
- **Decision**: RESOLVED — Fix A (align credentials). `docker-compose.yml`, `devcontainer.json`, `.env.example`, and MCP/script defaults updated to `postgres:postgres@postgres:5432/adr_flow` to match the existing Postgres volume (no volume recreation).

### F2 — Progress checkboxes marked done without commit SHAs

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: `context/changes/persistence-scaffold/plan.md:543-549`
- **Detail**: Phase 3 automated items 3.1–3.7 are `[x]` but lack ` — <commit sha>` annotations (Phases 1–2 include SHAs). Phase 3 work is still uncommitted in the working tree. Checkboxes were likely marked before commit or before verifying with the default devcontainer URL.
- **Fix**: After committing Phase 3, append commit SHA to each checkbox; uncheck any item that fails under default devcontainer `DATABASE_URL` until F1 is resolved.
- **Decision**: PENDING

### F3 — Migration integration tests omit live DB index/constraint checks

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: `backend/tests/infrastructure/adapters/persistence/test_migrations.py:35-37`
- **Detail**: `test_migrations.py` asserts table presence and `review_annotations` nullability on a migrated DB, but does not verify `users.email` uniqueness, `ix_adrs_user_id`, or event replay indexes at the database level. `test_models.py` covers metadata only. A migration that dropped indexes would not be caught by integration tests.
- **Fix**: Add inspector assertions for unique constraint on `users.email` and indexes `ix_adrs_user_id`, `ix_events_aggregate`, `ix_events_processed_at` in `test_migrations.py`.
- **Decision**: PENDING

### F4 — No foreign key on adrs.user_id

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality
- **Location**: `backend/infrastructure/adapters/persistence/models.py:52`, `migrations/versions/001_initial_events_users_adrs.py:57`
- **Detail**: `adrs.user_id` is a plain UUID column with no `ForeignKey("users.id")`. Research notes ownership is enforced in the application layer; plan does not require FK. Orphan ADR rows are possible if a projector bug writes a non-existent owner.
- **Fix**: Defer FK to a later slice when repositories/projectors land, or add `ForeignKey("users.id", ondelete="RESTRICT")` now if DB-level integrity is preferred for MVP.
- **Decision**: PENDING

### F5 — database_url.py extracted module (unplanned but aligned)

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: `backend/infrastructure/adapters/persistence/database_url.py`
- **Detail**: Plan specified normalization in `env.py` only. Implementation extracts `normalize_database_url()` for reuse in tests. No repositories, ports, or API surface added. Reasonable refactor.
- **Fix**: No action required; optionally note in plan addendum.
- **Decision**: PENDING

## What passed (no findings)

- **Security**: No dynamic SQL; `DATABASE_URL` not logged in `env.py`.
- **Schema contract**: All planned columns, JSONB nullability, soft-delete via `is_deleted`, event indexes present in ORM and migration.
- **PG15 compatibility**: Standard types only; `alembic check` passes.
- **Architecture boundaries**: No repositories, ports, projectors, or API routes introduced.
- **Plan "not doing" list**: Respected.

## Files in Phase 3 scope (working tree)

| File | Status |
|------|--------|
| `backend/infrastructure/adapters/persistence/models.py` | Modified |
| `backend/infrastructure/adapters/persistence/migrations/env.py` | Modified |
| `backend/infrastructure/adapters/persistence/migrations/versions/001_initial_events_users_adrs.py` | New |
| `backend/infrastructure/adapters/persistence/database_url.py` | New (extra) |
| `backend/tests/infrastructure/adapters/persistence/*` | New |
| `backend/README.md` | Modified |

## Next steps

1. Resolve F1 (DATABASE_URL) so default devcontainer workflow passes.
2. Commit Phase 3 and update plan Progress with SHAs (F2).
3. Optionally strengthen migration integration tests (F3).
4. Complete manual verification 3.8–3.10 in the plan after inspecting local DB.
5. Proceed to Phase 4 (CI and GCP migration execution).
