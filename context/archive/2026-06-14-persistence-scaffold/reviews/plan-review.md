<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Persistence Scaffold Implementation Plan

- **Plan**: context/changes/persistence-scaffold/plan.md
- **Mode**: Deep
- **Date**: 2026-06-14
- **Verdict**: REVISE
- **Findings**: 0 critical, 4 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | WARNING |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

Grounding: 5/5 paths ✓, 4/4 symbols ✓, brief↔plan ✓

## Findings

### F1 — `deploy-web` can run when migration fails

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots
- **Location**: Phase 4 — Deploy Workflow job ordering
- **Detail**: Phase 4 gates `deploy-api` with `needs.migrate-api.result == 'success'`. When migration fails, `deploy-api` is skipped (not failed). Existing `deploy-web` already treats `deploy-api.result == 'skipped'` as OK (`.github/workflows/deploy-gcp.yml:71-74`). On a push that touches both `backend/**` and `frontend/**`, a failed `migrate-api` leaves `deploy-api` skipped and `deploy-web` can still run — violating the plan's "do not deploy until migration succeeds" intent for the whole release.
- **Fix A ⭐ Recommended**: Tighten `deploy-web` `if` so skipped `deploy-api` is OK only when `api` filter was false, and require `migrate-api.result == 'success'` when `api` was true.
  - Strength: One conditional change; preserves today's "web-only push" behavior; blocks partial deploy on combined pushes.
  - Tradeoff: Slightly more complex `if` expression.
  - Confidence: HIGH — matches existing `deploy-web` skip pattern and GHA `needs.*.result` semantics.
  - Blind spot: None significant.
- **Fix B**: Make `deploy-api` fail (not skip) when `migrate-api` fails
  - Strength: `deploy-web`'s existing check would block automatically.
  - Tradeoff: Failing jobs on false `if` are awkward in GHA; worse UX than an explicit `deploy-web` guard.
  - Confidence: MEDIUM — depends on whether you add a no-op failure step.
  - Blind spot: Job graph readability for future editors.
- **Decision**: PENDING

### F2 — Current State Analysis is stale

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Current State Analysis
- **Detail**: The section still says there is no `infrastructure/` package and no SQLAlchemy/Alembic/driver deps, but Phase 1 is complete on disk: `backend/infrastructure/adapters/persistence/`, `backend/alembic.ini`, `env.py` URL normalization, and `pyproject.toml` deps (`alembic`, `sqlalchemy`, `psycopg`) all exist. `/implement` starting at Phase 2 may misread the baseline.
- **Fix**: Refresh Current State to "Phase 1 complete; Phases 2–4 pending" and list what already landed vs what remains.
- **Decision**: PENDING

### F3 — Foundation doc drift (events + F-02 scope)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architectural Fitness
- **Location**: Phase 2 domain + Phase 3 schema (cross-doc)
- **Detail**: `application-architecture.md:118` omits `ADRContentUpdated`; the `adrs` projection table (`:99-100`) omits `review_annotations` and `reviewed_at`. F-02 scope there (`:190`) still lists ports, bootstrap, and dispatcher — all explicitly deferred in this plan. The plan closes the event/schema gaps in code but has no phase to update the architecture doc. Later slice implementers may treat `:118` as canonical.
- **Fix A ⭐ Recommended**: Add a short "Doc reconciliation" bullet to Phase 4 (or a follow-up note in References): update `application-architecture.md` events list, `adrs` columns, and F-02 scope to match narrowed F-02.
  - Strength: Single source of truth for agents and humans.
  - Tradeoff: Small extra edit outside backend code.
  - Confidence: HIGH — frame.md already flags this (`:68`).
  - Blind spot: None significant.
- **Fix B**: Leave architecture doc unchanged; rely on plan/research only
  - Strength: Zero doc churn in F-02.
  - Tradeoff: Recurring confusion until a later slice updates the doc.
  - Confidence: HIGH — known pattern, just deferred risk.
  - Blind spot: Agents reading architecture before plan may drift.
- **Decision**: PENDING

### F4 — Schema contract leaves implementer guesses

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 — ORM Table Metadata
- **Detail**: Research calls for `user_id` FK/index (`research.md:170`) and frame notes omissions: explicit FK, `is_deleted` default, UUID column types (`frame.md:33`). Phase 3 lists columns but not types, defaults, or whether `adrs.user_id` is a formal FK — implementer must decide ad hoc.
- **Fix**: Add one contract line each for UUID column types, `is_deleted` default `false`, and FK vs index-only on `adrs.user_id`.
- **Decision**: PENDING

### F5 — Cloud Run Job command wiring is hand-wavy

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 4 — `deploy-migrate-api.sh`
- **Detail**: Phase 4 says to run `uv run alembic upgrade head` via job command/args but leaves exact `gcloud run jobs deploy` flags as "per current syntax." API deploy relies on buildpack entrypoint; jobs need explicit `--command`/`--args` and CWD = `backend/` (where `alembic.ini` lives). First implementer will likely need doc lookup.
- **Fix**: Pin one concrete example in the script contract, e.g. `--command=uv` `--args=run,alembic,upgrade,head` with `--source=backend` (same as `deploy-api.sh:49-50`).
- **Decision**: FIXED — pinned in Phase 4 `deploy-migrate-api.sh` contract

### F6 — Persistence tests vs `just test-backend` without Postgres

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 — Migration Tests
- **Detail**: Phase 3 allows persistence tests to skip when no test DB URL is set, but success criteria 3.5 run full `just test-backend`. Host-side runs without `DATABASE_URL`/Postgres could fail unless tests use an explicit `pytest.mark.skipif`. Devcontainer is fine (`DATABASE_URL` in `.devcontainer/devcontainer.json`).
- **Fix**: State in the test contract: use `skipif` when `DATABASE_URL` unset; fail (not skip) in CI where the service container sets it.
- **Decision**: PENDING

### F7 — Progress ↔ phases mechanically sound

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW
- **Dimension**: Plan Completeness
- **Location**: Progress section
- **Detail**: One `## Progress` block; four phases match body headings; every Success Criteria bullet has a Progress row; no stray checkboxes in phase bodies. Phase 1 steps correctly marked `[x]` with SHAs.
- **Fix**: None — recorded as pass.
- **Decision**: PENDING
