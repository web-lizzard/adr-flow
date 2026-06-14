# Persistence Scaffold Implementation Plan

## Overview

Implement the backend persistence foundation that later vertical slices can build on: versioned Postgres migrations, SQLAlchemy ORM table metadata, and pure domain vocabulary for the MVP `User` and `ADR` aggregates.

This plan deliberately stops before ports, repositories, projectors, API routes, auth, or command/query integration. F-02 creates the database and domain contracts; later slices attach behavior and user flows.

## Current State Analysis

The backend is still a health-only FastAPI scaffold. There is no `domain/`, `application/`, or `infrastructure/` package on disk, and `backend/pyproject.toml` has no Postgres driver, SQLAlchemy, or Alembic dependency.

The architecture already defines the desired backend shape: write-side facts live in an append-only `events` table, reads use `users` and `adrs` projections, and `domain/` stays pure Python. The research for this change confirms the MVP aggregate model: `User` is thin and write-once; `ADR` is the main consistency boundary, but F-02 should only introduce vocabulary and persistence schema, not lifecycle enforcement.

## Desired End State

After this plan, the backend has a working Alembic migration stack under `backend/infrastructure/adapters/persistence/migrations`, SQLAlchemy ORM metadata in `backend/infrastructure/adapters/persistence/models.py`, and an initial migration that creates `events`, `users`, and `adrs`.

The domain layer has `User` and `ADR` value objects, aggregate containers, and event classes that establish the vocabulary for later slices, including `ADRContentUpdated`. These domain types do not enforce business rules or invariants yet.

Local development, CI, and production deployment each have a migration path: `just` recipes for local use, ephemeral Postgres validation in GitHub Actions, and a Cloud Run Job-based production migration runner that reaches the private Postgres VM through the same network shape as the API.

### Key Discoveries:

- `backend/main.py` and `backend/tests/test_health.py` are the only backend implementation files today.
- `context/foundation/application-architecture.md` reserves `domain/user/`, `domain/adr/`, and `infrastructure/adapters/persistence/` as the backend paths this scaffold should follow.
- `context/changes/persistence-scaffold/research.md` recommends two aggregates, embedded ADR review annotations, and `events`, `users`, and `adrs` as the F-02 schema.
- `.cursor/rules/backend-architecture.mdc` says not to abstract a single SQL adapter prematurely, which supports skipping ports and repositories in this plan.
- `.devcontainer/docker-compose.yml` uses Postgres 16 locally, while `deploy/gcp/_common.sh` defaults production Postgres to 15, so migrations must stay PG15-compatible.

## What We're NOT Doing

- No application ports, repositories, projectors, event store adapter, or query adapters.
- No FastAPI routes, auth flows, request/response schemas, or UI work.
- No command/query handlers and no event dispatch implementation.
- No business logic, invariants, status transition methods, ownership checks, or validation beyond lightweight value-object construction where it is purely representational.
- No workspaces, organizations, re-review history, configurable ADR rules, or separate review aggregate.
- No destructive or data-rewriting migrations.

## Implementation Approach

Use Alembic and SQLAlchemy as the backend persistence scaffold. SQLAlchemy metadata provides a single source for table structure, while Alembic provides migration history, fresh/existing database application, and CI/deploy commands.

Place SQL-related files under `backend/infrastructure/adapters/persistence/`:

- `models.py` for ORM table metadata.
- `migrations/` for Alembic config, environment, templates, and revision files.

Create pure domain packages under `backend/domain/user/` and `backend/domain/adr/`. These packages define IDs, enums, value objects, aggregate data containers, and event classes, but intentionally avoid lifecycle methods and invariants until slices S-01 and S-02 introduce actual behavior.

## Critical Implementation Details

### Migration Execution

Production migrations must not connect directly from a public GitHub runner to the private Postgres VM. The deploy path should use a stable Cloud Run Job that mirrors the API service account, `DATABASE_URL` Secret Manager binding, VPC egress, network, and subnet configuration.

### Domain Scope

F-02 domain files are vocabulary, not behavior. If an implementer starts adding transition methods such as `submit_for_review()` or enforcing status rules, that logic belongs in later slices and should be deferred.

### Postgres Compatibility

Local dev currently runs Postgres 16 and production defaults to Postgres 15. The initial migration should avoid PG16-only syntax and use ordinary PG15-compatible constructs.

### Alembic `DATABASE_URL` Driver Normalization

Production `db-url` in Secret Manager uses `postgresql+asyncpg://…` (see `deploy/gcp/04-secrets.sh`) because the API runtime is async. Alembic runs synchronously and needs a sync driver (`postgresql+psycopg://…` or `postgresql://…` with psycopg installed in Phase 1).

`backend/infrastructure/adapters/persistence/migrations/env.py` must normalize `DATABASE_URL` at load time: strip `+asyncpg`, map to the sync driver chosen in Phase 1, and never log the full URL. The same normalization applies in CI (sync URL), local dev (`postgresql://dev:dev@postgres:5432/app`), and the Cloud Run migration job (async URL from Secret Manager).

## Phase 1: Persistence Tooling & Package Layout

### Overview

Add the backend database dependencies and create the empty persistence adapter package structure that will hold SQLAlchemy models and Alembic migrations.

### Changes Required:

#### 1. Backend Dependencies

**File**: `backend/pyproject.toml`

**Intent**: Add the runtime dependencies needed for Postgres access, ORM metadata, and versioned migrations.

**Contract**: Runtime dependencies include SQLAlchemy, Alembic, and a Postgres driver compatible with both local `postgresql://...` URLs and production `postgresql+asyncpg://...` or the chosen normalized URL form. Preserve `[tool.uv].exclude-newer = "7 days"` and refresh `backend/uv.lock` through `uv`.

#### 2. Persistence Adapter Package

**File**: `backend/infrastructure/adapters/persistence/__init__.py`

**Intent**: Establish the persistence adapter package without implementing ports or repository behavior.

**Contract**: Package exists and is importable. It should not expose repository, event-store, projection, or application port APIs in F-02.

#### 3. Alembic Migration Package

**File**: `backend/infrastructure/adapters/persistence/migrations/`

**Intent**: Configure Alembic to run from the backend package and load SQLAlchemy metadata from `models.py`.

**Contract**: Include the Alembic environment, revision template if needed, and a `versions/` directory. Configuration must read `DATABASE_URL` at execution time rather than hardcoding local or production credentials. `env.py` must normalize `postgresql+asyncpg://` URLs to the sync driver chosen in Phase 1 dependencies (see Critical Implementation Details).

#### 4. Local Migration Recipes

**File**: `Justfile`

**Intent**: Give developers stable commands for applying migrations and checking migration state.

**Contract**: Add backend migration recipes that run from `backend/`, use `uv run alembic`, and rely on `DATABASE_URL` from the devcontainer or caller environment.

### Success Criteria:

#### Automated Verification:

- Dependency lock refresh succeeds: `cd backend && uv lock`
- Backend imports remain valid: `cd backend && uv run python -c "import main"`
- Alembic CLI can load configuration without connecting when asked for help/history: `cd backend && uv run alembic --help`
- Backend tests still pass: `just test-backend`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- New files are under the architecture-aligned path `backend/infrastructure/adapters/persistence/`.
- No ports, repositories, projectors, or event-store adapters were introduced.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Domain Vocabulary Scaffold

### Overview

Add pure Python domain vocabulary for the two MVP aggregates without implementing business behavior.

### Changes Required:

#### 1. User Domain Package

**File**: `backend/domain/user/`

**Intent**: Define the `User` aggregate vocabulary needed by account registration slices.

**Contract**: Include value objects and data containers for `UserId`, `EmailAddress`, `PasswordHash`, `User`, and `UserRegistered`. The package must not import FastAPI, SQLAlchemy, Pydantic, Alembic, or infrastructure code.

#### 2. ADR Domain Package

**File**: `backend/domain/adr/`

**Intent**: Define the `ADR` aggregate vocabulary needed by authoring, review, publish, and soft-delete slices.

**Contract**: Include value objects and data containers for `AdrId`, `AdrStatus`, `AdrTitle`, `AdrContent`, `ReviewAnnotation`, `ReviewResult`, `ADR`, and the event classes `ADRCreated`, `ADRContentUpdated`, `ADRSubmittedForReview`, `AIReviewCompleted`, `ADRPublished`, and `ADRSoftDeleted`.

#### 3. Domain Package Tests

**File**: `backend/tests/domain/`

**Intent**: Lock the thin-domain contract so future implementers know F-02 added vocabulary only.

**Contract**: Tests should verify importability, enum/event names, simple construction, and pure-Python dependency boundaries. They should not assert lifecycle transitions, ownership checks, email uniqueness, or status-machine behavior.

### Success Criteria:

#### Automated Verification:

- Domain tests pass: `cd backend && uv run pytest tests/domain`
- Full backend tests pass: `just test-backend`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- Domain code contains no SQLAlchemy, Alembic, FastAPI, Pydantic, or HTTP imports.
- Aggregates do not contain lifecycle methods or invariant enforcement.
- `ADRContentUpdated` is present in the event vocabulary and called out as the intentional architecture gap closure.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Schema Models, Initial Migration, and Local Verification

### Overview

Define the SQLAlchemy table metadata and initial Alembic migration for the event log and read projections, then verify that the migration applies locally on fresh and existing databases.

### Changes Required:

#### 1. ORM Table Metadata

**File**: `backend/infrastructure/adapters/persistence/models.py`

**Intent**: Define the database schema contract in one importable metadata module.

**Contract**: Define `events`, `users`, and `adrs` tables. The module should not implement repositories or query functions.

The schema contract is:

- `events`: append-only source of truth with `id`, `aggregate_type`, `aggregate_id`, `event_type`, `payload`, `occurred_at`, and `processed_at`.
- `users`: projection with `id`, `email`, `password_hash`, and `created_at`; `email` is unique.
- `adrs`: projection with `id`, `user_id`, `title`, `content`, `status`, `review_annotations`, `is_deleted`, `created_at`, `updated_at`, and nullable `reviewed_at`.

#### 2. Initial Alembic Revision

**File**: `backend/infrastructure/adapters/persistence/migrations/versions/`

**Intent**: Create the first versioned migration that establishes the persistence contract.

**Contract**: Migration creates the three tables, indexes needed for per-user ADR listing and event replay, a unique constraint/index for `users.email`, and PG15-compatible JSONB columns for event payloads and ADR review annotations.

#### 3. Migration Tests

**File**: `backend/tests/infrastructure/adapters/persistence/`

**Intent**: Verify the migration and metadata stay coherent.

**Contract**: Add tests for metadata table/column definitions and migration application against a database URL supplied by the test environment. Tests that require Postgres should fail clearly in CI if the service is unavailable and may skip locally when no test database URL is set.

#### 4. Local Documentation

**File**: `backend/README.md`

**Intent**: Document how to run migrations locally and what `DATABASE_URL` should point to in the devcontainer.

**Contract**: Include the devcontainer database URL, the new `just` recipes, and the distinction between migration commands and application runtime persistence.

### Success Criteria:

#### Automated Verification:

- Initial migration applies on a fresh dev database: `just migrate-backend`
- Re-running the migration command on an up-to-date database succeeds: `just migrate-backend`
- Migration current-state check passes: `cd backend && uv run alembic current --check-heads`
- Persistence tests pass with a Postgres test URL: `cd backend && uv run pytest tests/infrastructure/adapters/persistence`
- Full backend tests pass: `just test-backend`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- Inspect the local database and confirm `events`, `users`, and `adrs` exist with the expected columns.
- Confirm `adrs.review_annotations` is JSONB and nullable.
- Confirm soft delete is represented by `adrs.is_deleted` and does not remove ownership or status columns.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: CI and GCP Migration Execution

### Overview

Add automated migration validation for pull requests and a production-safe migration runner that executes inside GCP rather than connecting to the private database from GitHub directly.

This phase wires two distinct migration paths (research follow-up §Recommended CI/CD Shape):

1. **PR CI** — ephemeral `postgres:15-alpine` service on GitHub-hosted runners; validates that the migration set applies cleanly on a fresh database without touching shared infrastructure.
2. **Production deploy** — after WIF auth, a stable Cloud Run Job on the private VPC runs `alembic upgrade head` against the GCE Postgres VM; only on success does `deploy-api` publish a new API revision.

GitHub-hosted runners must **never** connect to the production Postgres VM. The firewall allows only Cloud Run subnet `10.8.0.0/24` (`deploy/gcp/02-network.sh`).

### Changes Required:

#### 1. PR Backend CI Workflow

**File**: `.github/workflows/backend-ci.yml` (new)

**Intent**: Gate pull requests that touch backend persistence with a fresh-database migration run on Postgres 15 (production parity).

**Contract**:

- **Trigger**: `on.pull_request` to `main` with `paths` filter covering at least:
  - `backend/**`
  - `.github/workflows/backend-ci.yml`
- **Concurrency**: `group: backend-ci-${{ github.event.pull_request.number }}`, `cancel-in-progress: true` so newer pushes supersede stale runs on the same PR.
- **Permissions**: `contents: read` only (no GCP auth in PR CI).
- **Service container** (job-level `services.postgres`):
  - Image: `postgres:15-alpine` (not 16 — matches `POSTGRES_VERSION` in `deploy/gcp/_common.sh`).
  - Env: `POSTGRES_USER=ci`, `POSTGRES_PASSWORD=ci`, `POSTGRES_DB=adrflow_test`.
  - Port mapping: host `5432` → container `5432`.
  - Health check: `pg_isready` with the same user/db; `options: --health-interval 5s --health-timeout 5s --health-retries 10`.
- **Job env**: `DATABASE_URL=postgresql://ci:ci@localhost:5432/adrflow_test` (sync URL; no `+asyncpg`).
- **Steps** (in order):
  1. `actions/checkout@v5`
  2. Install uv (match existing project convention — e.g. `astral-sh/setup-uv` with version from `backend/.python-version` or repo pin).
  3. `cd backend && uv sync --frozen`
  4. `cd backend && uv run alembic upgrade head`
  5. `cd backend && uv run alembic current --check-heads`
  6. `cd backend && uv run alembic check` (metadata drift guard once `models.py` exists from Phase 3)
  7. `cd backend && uv run pytest tests/infrastructure/adapters/persistence tests/domain`
  8. `cd backend && uv run ruff check .`
  9. `cd backend && uv run ty check`
- **Out of scope for this workflow**: GCP deploy, frontend lint, full `just test-backend` if it would duplicate unrelated suites — persistence + domain + static checks are sufficient for PR gate.

#### 2. Deploy Workflow — Concurrency, Path Filters, and Job Ordering

**File**: `.github/workflows/deploy-gcp.yml`

**Intent**: Serialize production deploys, detect migration-relevant changes, run migrations before API deploy, and keep web deploy ordering intact.

**Contract**:

- **Workflow-level concurrency** (add near top, after `name:`):
  - `group: deploy-gcp-${{ github.ref }}`
  - `cancel-in-progress: false` — do not cancel an in-flight migration + deploy; queue instead.
- **Extend `on.push.paths`** and the `dorny/paths-filter` `api` filter to include migration artifacts:
  - `backend/infrastructure/adapters/persistence/migrations/**`
  - `deploy/gcp/run-migrate-api.flags`
  - `deploy/gcp/deploy-migrate-api.sh`
- **New job `migrate-api`** (runs before `deploy-api` when API changes):
  - `needs: changes`
  - `if: needs.changes.outputs.api == 'true'`
  - Same WIF auth + `setup-gcloud` pattern as existing `deploy-api` job.
  - Single step: `bash deploy/gcp/deploy-migrate-api.sh`
  - On failure: workflow stops; `deploy-api` must not run (`needs: migrate-api` with `if: success()`).
- **Update `deploy-api`**:
  - `needs: [changes, migrate-api]`
  - `if: needs.changes.outputs.api == 'true' && needs.migrate-api.result == 'success'`
- **Update `deploy-web`** — add `migrate-api` to `needs` and tighten `if` so a skipped `deploy-api` (after migration failure) does not allow web deploy on combined pushes:
  - `needs: [changes, deploy-api, migrate-api]`
  - `if:` (multiline):
    ```yaml
    always() &&
    needs.changes.outputs.web == 'true' &&
    (
      needs.deploy-api.result == 'success' ||
      (needs.deploy-api.result == 'skipped' && needs.changes.outputs.api != 'true')
    ) &&
    (
      needs.changes.outputs.api != 'true' ||
      needs.migrate-api.result == 'success'
    )
    ```
  - **Rationale**: when `api` is true and `migrate-api` fails, `deploy-api` is skipped (not failed). The old `deploy-api.result == 'skipped'` check would still let `deploy-web` run. Require `migrate-api.result == 'success'` whenever `api` changed; allow `deploy-api` skipped only when `api` did not change (web-only push).
- **First-time bootstrap note**: if GCP scripts `01`–`06` have not been run, `migrate-api` will fail at auth or missing SA — document in README; not a workflow design change.

#### 3. Cloud Run Migration Job Flags

**File**: `deploy/gcp/run-migrate-api.flags` (new)

**Intent**: Hold static `gcloud run jobs deploy` flags for the migration job, parallel to `run-api.flags`.

**Contract**:

- **Mirror from API** (copy networking + region):
  - `--region=europe-west1` (overridden at runtime by script like `deploy-api.sh`)
  - `--vpc-egress=private-ranges-only`
  - `--network=default`
  - `--subnet=adr-flow-cloud-run`
- **Secrets**: `--set-secrets=DATABASE_URL=db-url:latest` only — migration job does not need `OPENROUTER_API_KEY`.
- **Omit** (API service-only flags):
  - `--allow-unauthenticated`
  - `--min-instances`, `--max-instances`, `--no-cpu-throttling`, `--cpu-boost`
- **Job execution** (set in script, not flags file): `--tasks=1`, `--parallelism=1`, `--max-retries=0` (or `1` if transient VPC blips are a concern — prefer fail-fast for schema changes).

#### 4. Cloud Run Migration Job Script

**File**: `deploy/gcp/deploy-migrate-api.sh` (new)

**Intent**: Create or update a stable Cloud Run Job and execute it synchronously on every API deploy.

**Contract**:

- **Stable job name**: `MIGRATE_JOB_NAME="${MIGRATE_JOB_NAME:-adr-flow-api-migrate}"` (document in README).
- **Source `_common.sh`** like `deploy-api.sh`; call `gcp_load_env`, `gcp_require_gcloud`, `gcp_set_project`.
- **Runtime SA**: same as API — `API_RUN_SA_EMAIL` from `04-secrets.sh` (`adr-flow-api-run@…`). Verify SA exists before deploy.
- **Flags file**: read `deploy/gcp/run-migrate-api.flags` with the same comment-stripping pattern as `deploy-api.sh`; substitute `--region` and `--subnet` from env.
- **Job deploy** (`gcloud run jobs deploy`) — pin these flags (mirror `deploy-api.sh`; do not rely on buildpack entrypoint):
  - `--source "${WORKSPACE_ROOT}/backend"` — build context and container working directory (where `alembic.ini` lives)
  - `--set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv`
  - `--service-account="${API_RUN_SA_EMAIL}"`
  - `--command=uv`
  - `--args=run,alembic,upgrade,head`
  - Apply VPC/secrets flags from `run-migrate-api.flags` (same substitution pattern as API deploy).
  - **Example** (region/subnet from env; flags file stripped of comments):
    ```bash
    gcloud run jobs deploy "${MIGRATE_JOB_NAME}" \
      --source "${WORKSPACE_ROOT}/backend" \
      --project="${GCP_PROJECT_ID}" \
      --region="${GCP_REGION}" \
      --set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv \
      --service-account="${API_RUN_SA_EMAIL}" \
      --command=uv \
      --args=run,alembic,upgrade,head \
      "${DEPLOY_FLAGS[@]}"
    ```
- **Job execute** (same script, after deploy succeeds):
  - `gcloud run jobs execute "${MIGRATE_JOB_NAME}" --project=… --region=… --wait`
  - Exit non-zero if execution fails; print log tail hint: `gcloud run jobs executions list --job=…` and `gcloud logging read` filter.
- **Idempotency**: `alembic upgrade head` on an up-to-date DB is a no-op — safe to run on every deploy even when only non-migration backend files changed.
- **Shellcheck**: script must pass `bash -n deploy/gcp/deploy-migrate-api.sh`.

#### 5. Local Migration Job Recipe

**File**: `Justfile`

**Intent**: Give operators a manual path to run the same migration job outside CI (break-glass, pre-deploy verification).

**Contract**:

- Add `gcp-migrate-api` recipe that runs `bash deploy/gcp/deploy-migrate-api.sh` with the same env expectations as `gcp-deploy-api` (authenticated `gcloud`, project/region from `.env` or bootstrap state).
- Document that this hits **production** (or whichever project `GCP_PROJECT_ID` points at) — not the devcontainer Postgres.

#### 6. GCP Migration Documentation

**File**: `deploy/gcp/README.md`

**Intent**: Document the normal migration path, CI vs production distinction, and manual break-glass operations.

**Contract** — add a **Database migrations** section covering:

- **Why not GitHub → Postgres VM**: private GCE IP, firewall scoped to `10.8.0.0/24`, `DATABASE_URL` uses internal IP.
- **PR CI**: `backend-ci.yml` + ephemeral Postgres 15; does not use Secret Manager or VPC.
- **Production**: `migrate-api` job in `deploy-gcp.yml` → `deploy-migrate-api.sh` → Cloud Run Job `adr-flow-api-migrate` → `alembic upgrade head`.
- **Alembic URL**: production secret is `postgresql+asyncpg://…`; `env.py` normalizes to sync driver (see plan Critical Implementation Details).
- **Operations**:
  - Manual run: `just gcp-migrate-api`
  - Inspect logs: `gcloud run jobs executions list --job=adr-flow-api-migrate --region=…` and Cloud Logging filter on job name.
  - Failure handling: fix migration, re-run job; do not deploy API until migration succeeds. Schema rollback is not automatic with Cloud Run revision rollback — prefer forward-compatible migrations.
- **Connection budget**: VM `max_connections = 20`; migration job is single-task — no connection pool needed, but avoid parallel migration jobs (workflow concurrency enforces this).

#### 7. Cross-Reference in Backend README

**File**: `backend/README.md` (extend Phase 3 doc)

**Intent**: Point developers from local migration commands to CI and production paths.

**Contract**: Short subsection linking to `backend-ci.yml` (PR validation), `just gcp-migrate-api` (production job), and `deploy/gcp/README.md` (networking rationale). State that local devcontainer Postgres 16 is acceptable for day-to-day work but CI uses 15 for prod parity.

### Success Criteria:

#### Automated Verification:

- PR workflow file is valid YAML and path filters include `backend/**`: review `.github/workflows/backend-ci.yml`.
- On a test PR touching `backend/`, `backend-ci.yml` completes: service Postgres 15 healthy, `alembic upgrade head`, `alembic current --check-heads`, `alembic check`, persistence tests, ruff, ty all pass.
- Deploy workflow includes `concurrency`, `migrate-api` job, and `deploy-api` depends on successful migration: review `.github/workflows/deploy-gcp.yml`.
- Extended path filters include `backend/infrastructure/adapters/persistence/migrations/**`, `deploy/gcp/run-migrate-api.flags`, and `deploy/gcp/deploy-migrate-api.sh`.
- GCP migration script shell syntax passes: `bash -n deploy/gcp/deploy-migrate-api.sh`
- `just gcp-migrate-api` recipe exists and invokes `deploy-migrate-api.sh`.
- Backend tests pass: `just test-backend`
- Backend lint passes: `cd backend && uv run ruff check .`
- Backend type check passes: `cd backend && uv run ty check`

#### Manual Verification:

- Review `deploy-gcp.yml` job graph: `changes` → `migrate-api` → `deploy-api` → `deploy-web` (when applicable).
- Confirm `deploy-web` blocks when `api` changed and `migrate-api` failed (skipped `deploy-api` must not unblock web on combined pushes).
- Confirm `run-migrate-api.flags` mirrors API VPC/subnet/egress and omits `--allow-unauthenticated` and API scaling/CPU flags.
- Confirm migration job uses only `DATABASE_URL=db-url:latest` and `adr-flow-api-run` service account.
- In a GCP-enabled environment (bootstrap `01`–`06` complete), run `just gcp-migrate-api` once and confirm execution succeeds and `alembic_version` reflects head in production Postgres.
- Confirm `backend-ci.yml` uses `postgres:15-alpine`, not 16.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests:

- Domain package importability and pure-Python construction.
- `AdrStatus` values exactly match `draft`, `in_review`, `after_review`, and `proposed`.
- Domain event class names include all MVP events plus `ADRContentUpdated`.
- SQLAlchemy metadata defines the expected tables, columns, nullability, JSONB columns, and key indexes/constraints.

### Integration Tests:

- Alembic upgrade applies cleanly to a fresh Postgres database.
- Alembic current-head check passes after upgrade.
- Running upgrade again on an up-to-date database is safe.
- CI runs migrations against an ephemeral Postgres service rather than the shared dev or production database.

### Manual Testing Steps:

1. Run the new local migration command in the devcontainer.
2. Inspect the devcontainer Postgres database for `events`, `users`, and `adrs`.
3. Confirm `users.email` is unique and `adrs.user_id` is indexed for per-user listing.
4. Confirm `review_annotations` and event `payload` use JSONB.
5. Review deploy workflow ordering: `migrate-api` → `deploy-api`; confirm `backend-ci.yml` uses Postgres 15.
6. Run `just gcp-migrate-api` in GCP (after bootstrap) and inspect Cloud Run Job execution logs.

## Performance Considerations

The initial schema targets the MVP's small data volume. Add indexes for user lookup by email, ADR listing by owner, and unprocessed event replay via `processed_at`. Avoid speculative indexes for annotation search because annotations are embedded and read with the ADR in the MVP.

## Migration Notes

This is the first application schema migration, so it should be additive and safe on a fresh database. Existing databases may only contain Alembic metadata or no app tables; the migration should handle that normal case through Alembic versioning.

Do not rewrite or delete event rows in any migration. Future projection migrations may be rebuildable conceptually, but production still requires normal backup discipline before risky changes.

## References

- Related research: `context/changes/persistence-scaffold/research.md`
- Frame brief (Phase 4 contract tightening): `context/changes/persistence-scaffold/frame.md`
- Foundation issue: `context/changes/github-issues/F-02-persistence-scaffold.md`
- Architecture: `context/foundation/application-architecture.md`
- Backend architecture rule: `.cursor/rules/backend-architecture.mdc`
- Dev Postgres config: `.devcontainer/docker-compose.yml`
- API deploy flags to mirror: `deploy/gcp/run-api.flags`
- Existing deploy workflow: `.github/workflows/deploy-gcp.yml`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Persistence Tooling & Package Layout

#### Automated

- [x] 1.1 Dependency lock refresh succeeds: `cd backend && uv lock` — b8333d1
- [x] 1.2 Backend imports remain valid: `cd backend && uv run python -c "import main"` — b8333d1
- [x] 1.3 Alembic CLI can load configuration without connecting when asked for help/history: `cd backend && uv run alembic --help` — b8333d1
- [x] 1.4 Backend tests still pass: `just test-backend` — b8333d1
- [x] 1.5 Backend lint passes: `cd backend && uv run ruff check .` — b8333d1
- [x] 1.6 Backend type check passes: `cd backend && uv run ty check` — b8333d1

#### Manual

- [x] 1.7 New files are under the architecture-aligned path `backend/infrastructure/adapters/persistence/`. — b8333d1
- [x] 1.8 No ports, repositories, projectors, or event-store adapters were introduced. — b8333d1

### Phase 2: Domain Vocabulary Scaffold

#### Automated

- [x] 2.1 Domain tests pass: `cd backend && uv run pytest tests/domain`
- [x] 2.2 Full backend tests pass: `just test-backend`
- [x] 2.3 Backend lint passes: `cd backend && uv run ruff check .`
- [x] 2.4 Backend type check passes: `cd backend && uv run ty check`

#### Manual

- [x] 2.5 Domain code contains no SQLAlchemy, Alembic, FastAPI, Pydantic, or HTTP imports.
- [x] 2.6 Aggregates do not contain lifecycle methods or invariant enforcement.
- [x] 2.7 `ADRContentUpdated` is present in the event vocabulary and called out as the intentional architecture gap closure.

### Phase 3: Schema Models, Initial Migration, and Local Verification

#### Automated

- [ ] 3.1 Initial migration applies on a fresh dev database: `just migrate-backend`
- [ ] 3.2 Re-running the migration command on an up-to-date database succeeds: `just migrate-backend`
- [ ] 3.3 Migration current-state check passes: `cd backend && uv run alembic current --check-heads`
- [ ] 3.4 Persistence tests pass with a Postgres test URL: `cd backend && uv run pytest tests/infrastructure/adapters/persistence`
- [ ] 3.5 Full backend tests pass: `just test-backend`
- [ ] 3.6 Backend lint passes: `cd backend && uv run ruff check .`
- [ ] 3.7 Backend type check passes: `cd backend && uv run ty check`

#### Manual

- [ ] 3.8 Inspect the local database and confirm `events`, `users`, and `adrs` exist with the expected columns.
- [ ] 3.9 Confirm `adrs.review_annotations` is JSONB and nullable.
- [ ] 3.10 Confirm soft delete is represented by `adrs.is_deleted` and does not remove ownership or status columns.

### Phase 4: CI and GCP Migration Execution

#### Automated

- [ ] 4.1 PR workflow valid and path-filtered: `.github/workflows/backend-ci.yml`
- [ ] 4.2 PR CI passes on a backend-touching PR: Postgres 15 service, `alembic upgrade head`, `--check-heads`, `alembic check`, persistence tests, ruff, ty
- [ ] 4.3 Deploy workflow has concurrency, `migrate-api` job, and `deploy-api` depends on successful migration
- [ ] 4.4 Deploy path filters include migration artifacts (`migrations/**`, `run-migrate-api.flags`, `deploy-migrate-api.sh`)
- [ ] 4.5 GCP migration script shell syntax passes: `bash -n deploy/gcp/deploy-migrate-api.sh`
- [ ] 4.6 `just gcp-migrate-api` recipe exists
- [ ] 4.7 Backend tests pass: `just test-backend`
- [ ] 4.8 Backend lint passes: `cd backend && uv run ruff check .`
- [ ] 4.9 Backend type check passes: `cd backend && uv run ty check`

#### Manual

- [ ] 4.10 Review deploy job graph: `changes` → `migrate-api` → `deploy-api` → `deploy-web`
- [ ] 4.11 Confirm `run-migrate-api.flags` mirrors VPC/subnet/egress; omits public auth and API scaling flags
- [ ] 4.12 Confirm migration job uses `DATABASE_URL=db-url:latest` and `adr-flow-api-run` SA only
- [ ] 4.13 Run `just gcp-migrate-api` in GCP-enabled env and verify job execution + `alembic_version` at head
- [ ] 4.14 Confirm `backend-ci.yml` uses `postgres:15-alpine`
