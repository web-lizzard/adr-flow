---
date: 2026-07-05T19:00:00+02:00
researcher: Cursor Agent
git_commit: f61d702888e98075fc7cd76b290f7e9295e30019
branch: main
repository: adr-flow
topic: "Test-plan refresh — product drift, test-base growth, stale rollout phases"
tags: [research, test-plan, testing, adr-flow, ai-review, e2e]
status: complete
last_updated: 2026-07-05
last_updated_by: Cursor Agent
---

# Research: Test-Plan Refresh (2026-07-05)

**Date**: 2026-07-05
**Researcher**: Cursor Agent
**Git Commit**: f61d702888e98075fc7cd76b290f7e9295e30019
**Branch**: main
**Repository**: adr-flow

## Research Question

What changed since `context/foundation/test-plan.md` was written (2026-06-16) that requires a refresh — product requirements, test-base profile, existing coverage, and gaps against the user's north star (review flow end-to-end + auth e2e)?

## Summary

The guide is stale on three axes:

1. **Product model** — PRD now describes a **two-phase review**: deterministic static gap detection (score-0) plus **per-section LLM quality ratings (1–5)** and cross-section inconsistency/conciseness. The old plan framed Risk #1 as "false-positive annotations / strict validation"; the current wedge risk is **garbage or empty LLM ratings completing as `after_review`** because `validate_review_result` logs but does not block (`adr_review_service.py:113-118`).

2. **Test base** — grew from **sparse (~10 files)** to **meaningful (~57 backend + 14 frontend)**. Domain lifecycle, read-path IDOR, JWT unit tests, review schema/validator harness, handler failure → `review_failed`, and API retry flows already exist. Original §3 Phase 1 ("bootstrap pytest/vitest + domain unit tests") is **obsolete**; its change folder (`testing-critical-path-domain-auth`) was never created.

3. **Gaps for north star** — No Playwright/e2e harness. Frontend has strong Vitest coverage with mocks; `saveOnBlur()` in `useAdrPersistence.ts` is untested; mutating IDOR (PATCH/save/retry cross-user) and event/projection atomicity under failure remain open.

Recommended refresh: **5 risks**, **4 rollout phases** (API integration → AI contract/recovery → e2e auth + mocked-LLM north star → quality gates).

## Detailed Findings

### Product requirement drift

| Old assumption (guide) | Current PRD (2026-05-19) |
|------------------------|--------------------------|
| AI review = annotation schema + section detection | Static gaps (score 0) **then** parallel LLM per-section ratings 1–5 (`prd.md:112-113`, `prd.md:145-151`) |
| 4 statuses | 5 statuses incl. `review_failed` + retry (`prd.md:101-106`) |
| Strict validation as primary wedge | Merge validation is advisory; user sees `after_review` even with quality issues (`prd.md:153`) |

### Test-base profile

| Layer | Guide (2026-06-16) | Current |
|-------|-------------------|---------|
| Backend | 8 files, "effectively bare" | ~53 test modules under `backend/tests/` (~302 test functions) |
| Frontend | 2 files | 14 Vitest files in `frontend/tests/` |
| E2E | Excluded | Still none — no Playwright config or `e2e/` directory |

**Verdict:** `meaningful` — config + ~67 test files spread across domain, API, review quality, persistence, auth, and frontend components.

### Coverage vs refreshed risks

#### Risk: LLM garbage ratings

- **Strong:** `review_llm_schema.py` wire validation, `review_quality.py` runtime validator, `review_quality/` fixture harness, fake LLM service tests.
- **Gap:** `test_adr_api.py:452-511` asserts garbage ratings still land in `after_review` with empty `section_ratings`. Handler test `test_run_ai_review.py:236-268` confirms validation failure does not fail review.
- **Prove protection:** API/integration test that malformed or incomplete merged output either blocks completion or surfaces `review_failed` — not silent empty ratings.

#### Risk: Stuck in `in_review`

- **Strong:** Handler exception → `AIReviewFailed` (`run_ai_review.py:171-231`), projection `review_failed`, API flow `test_adr_api.py:705-759`, aggregate `fail_review`/`retry_review`.
- **Gap:** No test for unhandled worker crash leaving perpetual `in_review` without event drain; retry IDOR missing.

#### Risk: IDOR

- **Strong:** Cross-user GET/list/delete/review read paths in `test_adr_api.py`; repository owner scoping.
- **Gap:** PATCH, beacon `POST .../save`, `retry-review` cross-user; tampered JWT on ADR routes (only tested on `/api/auth/me`).

#### Risk: Persistence loss

- **Strong:** Backend PATCH/beacon API tests; frontend `pagehide` beacon test in `useAdrPersistence.test.ts`.
- **Gap:** `saveOnBlur()` untested; content blur → save untested; reload-after-blur scenario untested; event append + projection atomicity under failure untested.

#### Risk: Retry corruption

- **Strong:** Happy retry command + aggregate guards (`retry_adr_for_review.py`, `test_adr_aggregate.py:218-328`).
- **Gap:** Double-retry, concurrent retry, stale `review_error` after partial failure — no dedicated tests.

### Risks dropped from guide (with rationale)

| Old # | Risk | Why drop/reframe |
|-------|------|------------------|
| 2 | Illegal status transitions | Domain + API already well covered (`test_adr_aggregate.py`, `test_adr_api.py:228,682`) — not a top-5 gap |
| 5 | Projection staleness (append succeeds, project fails) | Still real but lower priority vs north-star e2e; can fold into Phase 1 API integration if time permits |
| 7 | JWT forgery | Unit + `/me` API covered; Phase 3 auth e2e extends to protected ADR routes |

### Hot-spot evidence (30d, `backend/` + `frontend/app/`)

| Directory | Touches | Relevance |
|-----------|---------|-----------|
| `backend/domain/adr` | 43 | Lifecycle + review domain |
| `backend/tests/infrastructure/api` | 33 | Test investment mirrors API risk |
| `backend/infrastructure/llm` | 28 | LLM rating adapter churn |
| `backend/tests/review_quality` | 17 | Review contract harness |
| `frontend/app/composables` | 15 | Persistence + API client |

### E2E / north-star gap

- No Playwright in `package.json` devDependencies or scripts.
- `adr-editor-page.test.ts` mocks store, polling, and persistence — good unit signal, not north-star.
- User north star: **login → create/edit → submit review → see ratings/annotations → publish** with **mocked LLM** at API boundary; plus **auth e2e** (register/login → workspace).

### Stale §3 state

- Phase 1 status was `change opened` → `testing-critical-path-domain-auth` but **folder does not exist** on disk.
- Phases 2–4 `not started`.
- All phase goals assume bootstrapping tests that largely already ship.

## Code References

- `backend/application/services/adr_review_service.py:64-120` — static + LLM merge; validation warn-only
- `backend/application/handlers/run_ai_review.py:95-231` — idempotency, success, failure paths
- `backend/tests/infrastructure/api/test_adr_api.py:357-511` — happy review + garbage-ratings acceptance
- `backend/tests/domain/test_adr_aggregate.py:96-328` — lifecycle + retry domain rules
- `frontend/app/composables/useAdrPersistence.ts` — `saveOnBlur`, `beaconSave` (only beacon tested)
- `frontend/tests/adr-editor-page.test.ts` — review UX with mocks
- `context/foundation/prd.md:112-153` — LLM rating model + advisory validation

## Architecture Insights

- Review pipeline: **Phase 0 static** → **parallel LLM** → **merge** → **advisory validate** → handler completes or fails on transport errors only.
- Recovery: per-call LLM retry (infra) vs user `retry-review` (domain) are separate concerns — test both independently.
- Frontend persistence: blur and unload are separate code paths; testing one does not cover the other.

## Historical Context

- `context/foundation/test-plan.md` (2026-06-16) — written when test base was sparse and strict-validation framing dominated Risk #1.
- `context/changes/test-plan-refresh-2026-07-05/change.md` — refresh trigger and brief from user.

## Open Questions

1. Should garbage LLM ratings **block** `after_review` (product change) or only **test/document** current advisory behavior? Research assumes tests encode desired behavior; product owner may need to decide if validation should hard-fail.
2. Playwright vs Vitest browser mode for Phase 3 e2e — no harness exists yet; plan should pick one and bootstrap in Phase 3 or Phase 4.

## Recommendations for refreshed guide

1. Update `test_base_profile` header to `meaningful`.
2. Replace §2 with 5 risks listed in change brief; refresh response guidance from findings above.
3. Reset §3 phases to 4 rows, all `not started`, no stale change folder.
4. Update §4 counts; note e2e `none yet — see §3 Phase 3`.
5. Expand §7 negative space per brief: no real-LLM e2e, no snapshots, no F-score eval, no full browser e2e for every transition.
6. Add §8 Freshness Ledger with today's date.
