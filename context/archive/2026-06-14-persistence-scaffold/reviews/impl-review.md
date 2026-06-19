<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Persistence Scaffold

- **Plan**: context/changes/persistence-scaffold/plan.md
- **Scope**: Phases 1–4 (full plan)
- **Date**: 2026-06-15
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Migration application tests missing from pytest suite

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: backend/tests/infrastructure/adapters/persistence/
- **Detail**: Phase 3 contract requires tests for "metadata table/column definitions **and migration application** against a database URL." `test_models.py` covers ORM metadata only (4 tests). `conftest.py` defines `postgres_url` and `db_engine` fixtures (L36–57) but no test consumes them. CI runs `alembic upgrade head` in `backend-ci.yml` (L47–49), so migrations are validated in workflow — but not in the pytest suite the plan specified. A prior phase-3 review referenced `test_migrations.py`; that file was never committed.
- **Fix**: Add `test_migrations.py` using `db_engine` that applies migrations (or assumes CI-applied state) and asserts via `inspect()` that tables, `users.email` uniqueness, and indexes `ix_adrs_user_id`, `ix_events_aggregate`, `ix_events_processed_at` exist on a live database.
- **Decision**: PENDING

### F2 — DBeast MCP dev tooling outside plan scope

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: .cursor/mcp.json, .devcontainer/post-create.d/19-mcp-dbeast.sh, scripts/mcp/*
- **Detail**: Commit `6215f1d` added DBeast PostgreSQL MCP wiring (~8 files) during persistence-scaffold work. Useful for local DB debugging but not in F-02 plan or "What We're NOT Doing" guardrails. Largest out-of-plan addition in the diff range `b8333d1^..HEAD`.
- **Fix A ⭐ Recommended**: Document as an addendum in the plan or change notes — acknowledge intentional dev-tooling bundled with persistence work.
  - Strength: Preserves useful tooling; updates source of truth.
  - Tradeoff: Plan becomes a slightly moving target.
  - Confidence: HIGH — tooling is self-contained and does not affect runtime.
  - Blind spot: Stakeholders who reviewed original F-02 scope are not notified.
- **Fix B**: Revert DBeast MCP changes to a separate change/PR for strict scope discipline.
  - Strength: Keeps F-02 diff focused on persistence.
  - Tradeoff: Loses debugging convenience; another PR needed.
  - Confidence: MEDIUM — depends whether team already relies on DBeast locally.
  - Blind spot: Haven't verified who uses the MCP server today.
- **Decision**: PENDING

### F3 — PR CI pytest subset omits health endpoint test

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: .github/workflows/backend-ci.yml:59-61
- **Detail**: CI runs `pytest tests/infrastructure/adapters/persistence tests/domain` but not `tests/test_health.py`, while `just test-backend` runs the full suite (12 tests). A regression in `main.py` or the health endpoint would not be caught on backend-only PRs.
- **Fix**: Add `tests/test_health.py` to the CI pytest invocation, or run `uv run pytest` for full parity with local `just test-backend`.
- **Decision**: PENDING

### F4 — Cloud Run Job command differs from plan contract

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: deploy/gcp/deploy-migrate-api.sh:54-63
- **Detail**: Plan specifies `--command=uv`, `--args=run,alembic,upgrade,head`, `--set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv`. Implementation uses `--command=launcher`, `--args=python,-m,alembic,upgrade,head` with comments explaining gcloud jobs limitations (L50–53). Functionally equivalent; documented in `deploy/gcp/README.md`. Plan contract text not followed literally.
- **Fix**: Add a one-line addendum to the plan Phase 4 section noting the launcher workaround, or update plan contract to match implementation.
- **Decision**: PENDING

### F5 — No foreign key on adrs.user_id

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality
- **Location**: backend/infrastructure/adapters/persistence/models.py:52
- **Detail**: `adrs.user_id` is a plain UUID with no `ForeignKey("users.id")`. Orphan ADR projection rows are possible if a projector bug writes a non-existent owner. Research and plan defer integrity to application layer; consistent with F-02 vocabulary-only scope.
- **Fix**: Defer FK to repository/projector slices (S-01/S-02), or add `ForeignKey("users.id", ondelete="RESTRICT")` in a follow-up migration if DB-level integrity is preferred for MVP.
- **Decision**: PENDING

### F6 — adrs.status is unconstrained at DB level

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/infrastructure/adapters/persistence/models.py:55
- **Detail**: `adrs.status` is `String(32)` with no CHECK constraint or Postgres enum. Any string can be written to the projection; domain `AdrStatus` enum is not enforced at DB level. Acceptable for F-02 scaffold; projectors will enforce later.
- **Fix**: No action for F-02; add CHECK constraint or Postgres enum when status vocabulary stabilizes in a behavior slice.
- **Decision**: PENDING

### F7 — --max-retries=0 lacks inline rationale

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: deploy/gcp/deploy-migrate-api.sh:63
- **Detail**: `--max-retries=0` differs from Cloud Run default (3). Fail-fast is correct for schema migrations, but only the block comment above (L50–53) explains jobs deploy constraints — not why retries are disabled. A future maintainer might bump retries without understanding partial-apply risk.
- **Fix**: Add a one-line comment above `--max-retries=0` explaining migrations should fail-fast for inspection.
- **Decision**: PENDING
