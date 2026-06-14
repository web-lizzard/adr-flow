# Frame Brief: Persistence Scaffold Plan — Cloud/CI Correctness

> Framing step before /plan. This document captures what is *actually*
> at issue, separated from what was initially assumed.

## Reported Observation

User has a written implementation plan (`plan.md`) for F-02 persistence scaffold and is not experienced in cloud and CI. They want to know whether the plan — especially Phase 4 — is correct before starting implementation.

## Initial Framing (preserved)

- **User's stated cause or approach**: The plan may be wrong or incomplete in cloud/CI areas; they need an expert sanity check because they lack confidence in those topics.
- **User's proposed direction**: Validate `plan.md` (referenced directly) before implementing.
- **Pre-dispatch narrowing**: Leading concern is **Phase 4 — CI workflows and the GCP Cloud Run migration job**.

## Dimension Map

The observation could originate at any of these dimensions:

1. **Cloud migration execution model** — whether production migrations should run from GitHub runners vs a GCP-side job on the private VPC network.
2. **CI workflow contract completeness** — whether Phase 4 specifies enough detail (triggers, Postgres version, path filters, concurrency) for a correct first implementation.
3. **Architecture scope alignment** — whether F-02 should include ports/bootstrap/dispatcher (per `application-architecture.md`) or only schema/migrations (per plan).
4. **Schema/domain technical correctness** — whether Phases 2–3 table and domain contracts match research and architecture.

## Hypothesis Investigation

| Hypothesis | Evidence | Verdict |
| --- | --- | --- |
| **Cloud Run Job is the wrong production migration path** | Postgres firewall allows only Cloud Run subnet `10.8.0.0/24` (`deploy/gcp/02-network.sh:30-38`, `postgres-vm-setup.sh:58-60`). API already uses Direct VPC egress + `DATABASE_URL` secret (`run-api.flags:13-17`, `04-secrets.sh:31-43`). Research explicitly rejects GitHub→VM (`research.md:204-206`). WIF deploy SA has `run.admin` (`05-wif-github.sh:19-26`). Plan Phase 4 matches research (`plan.md:53-55`, `260-274`). | **NONE** — opposite hypothesis; pattern is correct |
| **Cloud Run Job is the right path but infra doesn't support it yet** | Network, secrets, runtime SA, and WIF IAM exist. No migration script, flags file, workflow step, or `just migrate-backend` yet — expected Phase 4 deliverables, not a design flaw. | **STRONG** — pattern fits; implementation absent |
| **Phase 4 CI contract is underspecified** | Only `deploy-gcp.yml` exists today; no PR CI, no Postgres service, no concurrency (`deploy-gcp.yml:7-67`). Plan says "pull requests" and "as appropriate" but omits `on: pull_request`, PG15 service image, path filters for new migration files, Alembic `check`/`--check-heads`, concurrency group semantics (`plan.md:252-266`). Dev Postgres is 16, prod is 15 (`docker-compose.yml:25`, `_common.sh:29`). | **STRONG** |
| **Plan scope conflicts with architecture doc** | `application-architecture.md:190` requires ports, bootstrap, empty dispatcher. Plan excludes all (`plan.md:7`, `33-35`). F-02 issue and roadmap narrow to schema contract (`F-02-persistence-scaffold.md:16-22`, `roadmap.md:65-73`). `backend-architecture.mdc:37-38` discourages premature port abstraction. | **STRONG** mismatch exists; **deferring is defensible** for F-02 |
| **Phases 2–3 schema/domain are wrong** | Tables, events, JSONB annotations, `ADRContentUpdated`, PG15-compat align with research and architecture events spec (`plan.md:194-196`, `research.md:168-171`, `application-architecture.md:83-91`). Minor omissions: explicit FK, `is_deleted` default, UUID column types. | **NONE** for correctness; **WEAK** on migration contract detail |

## Narrowing Signals

- User's leading concern is Phase 4 cloud/CI, not schema design.
- Existing GCP bootstrap (subnet, firewall, secrets, WIF) already matches the Cloud Run Job pattern — no need to open Postgres to the public internet.
- `DATABASE_URL` in Secret Manager uses `postgresql+asyncpg://` (`04-secrets.sh:31`) while Alembic typically needs a sync driver — plan does not call this out; implementer must handle in `env.py`.
- Deploy workflow path filters omit future migration script/flags paths (`deploy-gcp.yml:10-17`) — backend-only migration changes could deploy API without running migrations unless filters are extended.

## Cross-System Convention

This repo's infrastructure decision (`infrastructure.md`, `deploy/gcp/README.md`) intentionally keeps Postgres private on a GCE VM reachable only from the Cloud Run subnet. CI convention elsewhere in the project is deploy-on-merge (`deploy-gcp.yml`); there is no PR test workflow yet (`AGENTS.md:44` is stale — deploy exists, tests do not).

The research follow-up (`research.md:196-270`) and plan Phase 4 follow the standard pattern for private databases: **validate migrations on ephemeral Postgres in CI; apply migrations from inside GCP before deploying the app**. That matches industry practice and this repo's network design.

## Reframed (or Confirmed) Problem Statement

> **The actual problem to plan around is**: Phase 4's cloud/CI **architecture is correct**, but the plan **contract is too thin** for someone inexperienced in cloud/CI — the right pattern (ephemeral Postgres PR CI + Cloud Run Job before API deploy) needs explicit workflow details before implementation, not a redesign.

The plan is not wrong about *what* to build for cloud/CI. It is under-specified about *how* to wire it: PR triggers, `postgres:15` service image, deploy path filters for migration artifacts, `concurrency` semantics, Alembic sync URL handling for `postgresql+asyncpg://`, and job image/revision alignment with the API deploy. Phases 1–3 are sound; a separate doc-scope tension (ports/bootstrap) exists but is not the user's leading concern and does not block cloud/CI work.

## Confidence

**MEDIUM-HIGH** for cloud/CI direction (STRONG on pattern, WEAK on contract detail). **HIGH** that the plan does not need a different cloud approach.

Specific verification before `/implement` Phase 4: confirm GCP bootstrap status (scripts 01–06) if manual migration-job testing is required in this change.

## What Changes for /plan

Do **not** replace Cloud Run Job with GitHub-runner-to-VM migrations. **Do** tighten Phase 4 contracts before or during implementation:

1. New workflow (e.g. `backend-ci.yml`): `on: pull_request` with path filters; `services: postgres:15-alpine`; steps for `alembic upgrade head`, `alembic current --check-heads`, persistence tests, ruff, ty.
2. Extend `deploy-gcp.yml`: `concurrency` group; migrate job before `deploy-api`; path filters for migration script/flags and Alembic revisions.
3. Document Alembic `env.py` handling of `postgresql+asyncpg://` → sync driver for migrations.
4. Migration job flags: mirror VPC/secrets/SA from `run-api.flags`; omit `--allow-unauthenticated` and service-only CPU flags; only `DATABASE_URL` secret needed.
5. Optionally reconcile `application-architecture.md:190` with narrowed F-02 scope (ports/bootstrap deferred) — separate from cloud/CI.

Phases 1–3 can proceed as written; Phase 4 implementer should treat the list above as required contract additions.

## References

- Plan under review: `context/changes/persistence-scaffold/plan.md`
- Research (CI/migration follow-up): `context/changes/persistence-scaffold/research.md:196-270`
- Deploy workflow (current): `.github/workflows/deploy-gcp.yml`
- API networking template: `deploy/gcp/run-api.flags`, `deploy/gcp/deploy-api.sh`
- Postgres network lockdown: `deploy/gcp/02-network.sh`, `deploy/gcp/postgres-vm-setup.sh`
- WIF IAM for job orchestration: `deploy/gcp/05-wif-github.sh`
- Architecture scope tension: `context/foundation/application-architecture.md:190`
- Investigation tasks: architecture scope, cloud migration, CI workflow, schema/domain sub-agents (2026-06-14)
