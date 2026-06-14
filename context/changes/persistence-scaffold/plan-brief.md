# Persistence Scaffold — Plan Brief

> Full plan: `context/changes/persistence-scaffold/plan.md`
> Frame brief: `context/changes/persistence-scaffold/frame.md`
> Research: `context/changes/persistence-scaffold/research.md`

## What & Why

Build the backend persistence foundation required before account access and ADR authoring can store real application state. F-02 adds the database schema, migration tooling, ORM metadata, and pure domain vocabulary while deliberately postponing ports, adapters, APIs, and business behavior to later vertical slices.

## Starting Point

The backend currently has only `GET /health`, one health test, and FastAPI/Uvicorn dependencies. Postgres exists in devcontainer and GCP infrastructure, but the backend has no driver, ORM models, migration stack, or domain packages.

## Desired End State

The backend has Alembic migrations under `backend/infrastructure/adapters/persistence/migrations`, SQLAlchemy table metadata in `backend/infrastructure/adapters/persistence/models.py`, and initial `events`, `users`, and `adrs` tables. The domain layer has thin `User` and `ADR` value objects, aggregate containers, and event classes without lifecycle logic or invariants. Local, CI, and production deployment paths can run migrations safely.

## Key Decisions Made

| Decision | Choice | Why | Source |
|---|---|---|---|
| Migration tooling | Alembic + SQLAlchemy ORM metadata | Gives versioned migrations, metadata drift checks, and a standard FastAPI/Postgres path. | Plan |
| SQL file location | `backend/infrastructure/adapters/persistence/migrations` | Matches the user's requested adapter nesting and keeps SQL concerns in infrastructure. | Plan |
| ORM metadata location | `backend/infrastructure/adapters/persistence/models.py` | Gives migrations a stable metadata source without creating repositories or ports. | Plan |
| Domain depth | Thin value objects, aggregates, and events only | Establishes vocabulary while leaving behavior and invariants to slices. | Plan |
| Review annotations | Nullable JSONB on `adrs` | Annotations are embedded in ADR for MVP and always read with the ADR. | Research / Plan |
| Event vocabulary | Include `ADRContentUpdated` | Editing needs an event in the event-sourced model even though the architecture list omitted it. | Research / Plan |
| Migration execution | Local command, ephemeral Postgres CI, and Cloud Run Job | Validates migrations before merge and runs production migrations from inside GCP private networking. | Research / Plan |
| PR CI Postgres version | `postgres:15-alpine` service container | Matches production GCE Postgres 15; devcontainer PG16 is not the CI contract. | Frame / Plan |
| Alembic URL in prod | `env.py` normalizes `postgresql+asyncpg://` → sync driver | Secret Manager URL targets async API runtime; Alembic needs sync psycopg. | Frame / Plan |
| Deploy concurrency | `group: deploy-gcp-${{ github.ref }}`, `cancel-in-progress: false` | Prevents overlapping migration jobs; queues deploys instead of cancelling mid-migration. | Frame / Plan |
| Migration job identity | Stable `adr-flow-api-migrate` Cloud Run Job | Predictable logs, IAM, and ops; updated on each deploy via `deploy-migrate-api.sh`. | Research / Plan |

## Scope

**In scope:**

- Backend DB dependencies and lock refresh.
- Alembic migration stack and initial migration.
- SQLAlchemy models for `events`, `users`, and `adrs`.
- Pure domain vocabulary for `User` and `ADR`.
- Local `just` migration recipes.
- CI migration validation with ephemeral Postgres.
- GCP-side migration job path before API deploy.

**Out of scope:**

- Ports, repositories, projectors, event-store adapter, and query adapters.
- FastAPI routes, auth flows, request/response schemas, and frontend work.
- Command/query handlers, event dispatch, and application bootstrap.
- Business logic, invariants, ownership checks, and ADR lifecycle transitions.
- Separate review aggregate, workspaces, configurable rules, or re-review history.

## Architecture / Approach

Use SQLAlchemy metadata as the schema contract and Alembic as the migration history runner. Keep SQL and migrations under the infrastructure adapter package, while domain types live under `backend/domain/user` and `backend/domain/adr` with no infrastructure imports. Production migration execution uses a stable Cloud Run Job that mirrors API networking, secrets, and service account access instead of connecting directly from GitHub-hosted runners to the private Postgres VM.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Persistence Tooling & Package Layout | Dependencies, Alembic package, and local migration recipes | Tooling drift or misplaced files outside the requested adapter path |
| 2. Domain Vocabulary Scaffold | Pure domain value objects, aggregate containers, and event classes | Accidentally adding business logic too early |
| 3. Schema Models, Initial Migration, and Local Verification | `events`, `users`, `adrs` metadata and first migration | Schema mismatch with later slices or PG16-only SQL |
| 4. CI and GCP Migration Execution | `backend-ci.yml` PR gate + `migrate-api` job before API deploy | Wrong Postgres version in CI, deploy path-filter gaps, or async URL breaking Alembic in prod job |

**Prerequisites:** Devcontainer Postgres or another `DATABASE_URL`; GCP deploy variables for production migration job validation.

**Estimated effort:** About 3-4 focused implementation sessions across 4 phases.

## Open Risks & Assumptions

- Production Postgres is PG15 while local dev is PG16, so migrations must stay PG15-compatible.
- The migration job can reuse or mirror the API runtime service account and Secret Manager access.
- Domain scaffolding is intentionally inert; future slices must add behavior rather than assuming F-02 enforces invariants.
- CI migration validation needs a Postgres service workflow that does not rely on the private production database.
- `env.py` must normalize async production `DATABASE_URL` before Alembic connects.
- Deploy path filters must include migration script/flags and Alembic revisions or backend-only migration changes could skip `migrate-api`.

## Success Criteria (Summary)

- Fresh and existing databases can run the initial migration cleanly.
- `events`, `users`, and `adrs` match the MVP ownership, lifecycle, content, annotation, timestamp, and soft-delete contract.
- Domain packages are pure Python and contain vocabulary only, with no ports/adapters or business behavior.
