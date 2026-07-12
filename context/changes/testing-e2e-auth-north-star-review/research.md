---
date: 2026-07-13T01:00:00+02:00
researcher: AI assistant
git_commit: 5634fccefc9406ca60988d7a5aeb5298c0b532b7
branch: main
repository: web-lizzard/adr-flow
topic: "Phase 3 — E2E auth + north-star review flow with mocked LLM"
tags: [research, codebase, e2e, playwright, north-star, fake-llm, auth]
status: complete
last_updated: 2026-07-13
last_updated_by: AI assistant
---

# Research: Phase 3 — E2E Auth + North-Star Review Flow

**Date**: 2026-07-13T01:00:00+02:00
**Researcher**: AI assistant
**Git Commit**: 5634fccefc9406ca60988d7a5aeb5298c0b532b7
**Branch**: main
**Repository**: web-lizzard/adr-flow

## Research Question

What is the current state of the codebase for implementing Phase 3 of the test plan — E2E auth + north-star review with mocked LLM? Map the full user journey through frontend and backend, assess the fake LLM boundary for deterministic assertions, and identify infrastructure gaps blocking real spec authoring.

## Summary

The codebase is ready for Phase 3. The frontend implements the complete north-star flow across 6 pages (login → workspace → editor → review → publish). The backend exposes all required API endpoints with a fully deterministic `LLM_PROVIDER=fake` boundary. Playwright infrastructure (config, auth setup, fixtures, browser install, noVNC for headed debugging) is in place. The primary gaps are: **zero spec files exist** (a seed spec was written, failed on form submission, and was deleted), no API test helpers, no review-completion waiter, no DB cleanup strategy, and `playwright-report/` + `test-results/` are not gitignored.

## Detailed Findings

### 1. North-Star Flow — Frontend

The full journey maps to 6 pages under `frontend/app/pages/`:

| Step | Route | Page file | Key action |
|------|-------|-----------|------------|
| Login | `/login` | `pages/login.vue` | Email/password form → `auth.login()` → sessionStorage token → `/workspace` |
| Workspace | `/workspace` | `pages/workspace/index.vue` | List ADRs, "New ADR" form → `adr.create()` |
| Create | (redirect) | — | `POST /api/adrs` → navigate to `/workspace/adr/:id` |
| Edit draft | `/workspace/adr/:id` | `pages/workspace/adr/[id].vue` | Markdown editor, save-on-blur via `useAdrPersistence` |
| Submit | (button) | — | "Publish for review" button → `submitForReview()` → status `in_review` |
| Poll | (auto) | — | `useAdrReviewPolling` polls `GET /review-status` every 3s |
| Review | (sidebar) | `AdrReviewSidebar.vue` / `AdrReviewAnnotations.vue` | Auto-opens on `after_review`; section ratings + annotations |
| Edit after review | `/workspace/adr/:id` | same page | Editor re-enabled, save-on-blur |
| Publish | (button) | — | "Publish" button → `publish()` → toast "ADR published as proposed" |

#### Auth architecture

- **Token storage**: `sessionStorage` key `adr-flow.access_token` (`frontend/composables/useAuthToken.ts`)
- **API auth**: Bearer header on all `apiFetch` calls (`frontend/composables/useApi.ts:96-106`)
- **Route guards**: `auth` middleware blocks unauthenticated access; `guest` middleware redirects authenticated users from login/register (`frontend/app/middleware/auth.ts`, `guest.ts`)
- **401 handling**: `apiFetch` clears auth + redirects to `/login` on any 401 (`useApi.ts:110-118`)
- **No logout button** exists — session ends on 401 or tab close (sessionStorage)
- **Auth middleware does not set `redirect` query** when bouncing to `/login`, though the login page supports it

#### Editor status matrix

| Status | Editor | Primary CTA | Review panel | Helper text |
|--------|--------|-------------|--------------|-------------|
| `draft` | Editable | "Publish for review" | Hidden | "Draft changes save when you click away…" |
| `in_review` | Read-only | None | Hidden (until error) | "This ADR is being reviewed…" + polling indicator |
| `after_review` | Editable | "Publish" | Auto-opens with ratings + annotations | "Edit based on review feedback…" |
| `review_failed` | Editable | None (retry in sidebar) | Auto-opens with error + "Try again" | "Edit based on review failure details…" |
| `proposed` | Editable | None | Shown if prior review data exists | "Changes save when you click away…" |

#### Key composables

| Composable | File | Role |
|------------|------|------|
| `useAdrPersistence` | `frontend/app/composables/useAdrPersistence.ts` | Save-on-blur + beacon save on tab close |
| `useAdrReviewPolling` | `frontend/app/composables/useAdrReviewPolling.ts` | 3s polling during `in_review`; full reload on `after_review` |
| `useAdrPublishFeedback` | `frontend/app/composables/useAdrPublishFeedback.ts` | Publish success toast |

### 2. North-Star Flow — Backend API

All routes mounted under `/api` via `backend/infrastructure/bootstrap.py:202-210`.

#### Endpoint cheat sheet

| Step | Method | Path | Status | Key response |
|------|--------|------|--------|--------------|
| Register | POST | `/api/auth/register` | 201 | `{ access_token }` |
| Login | POST | `/api/auth/login` | 200 | `{ access_token }` |
| Create ADR | POST | `/api/adrs` | 201 | `{ id }` |
| Get ADR | GET | `/api/adrs/{id}` | 200 | Full `AdrResponse` |
| Update ADR | PATCH | `/api/adrs/{id}` | 200 | Full `AdrResponse` |
| Beacon save | POST | `/api/adrs/{id}/save` | 204 | — |
| Submit review | POST | `/api/adrs/{id}/submit-review` | 202 | — |
| Poll review | GET | `/api/adrs/{id}/review-status` | 200 | `{ status, reviewed_at, review_error, annotation_counts }` |
| Retry review | POST | `/api/adrs/{id}/retry-review` | 202 | — |
| Publish | POST | `/api/adrs/{id}/publish` | 204 | — |

#### ADR response shape

```json
{
  "id": "uuid",
  "title": "string",
  "content": "string (markdown)",
  "status": "draft | in_review | after_review | proposed | review_failed",
  "created_at": "datetime",
  "updated_at": "datetime",
  "section_ratings": [
    { "section": "Context | Options | Decision | Status | Consequences",
      "score": 0-5, "feedback": "string" }
  ],
  "review_annotations": [
    { "kind": "missing_section | inconsistency | conciseness",
      "message": "string", "location": "string | null",
      "suggestion": "string | null" }
  ],
  "reviewed_at": "datetime | null",
  "review_error": { "source_event_id": "uuid", "message": "string",
                     "failed_at": "datetime", "kind": "string" } | null
}
```

#### Status transition diagram

```
draft ──submit──► in_review ──AI success──► after_review ──publish──► proposed
                      │                          ▲
                      └──AI failure──► review_failed ─┘ (retry-review)
```

#### Async review pipeline

1. `SubmitAdrForReviewCommandHandler` appends `ADRSubmittedForReview` event (synchronous)
2. `TaskGroupEventBus` background worker polls unprocessed events (`backend/infrastructure/events/task_group_bus.py`)
3. `EventDispatcher` routes `ADRSubmittedForReview` to `RunAiReviewHandler`
4. Handler calls `AdrReviewService.review_adr()` → appends `AIReviewCompleted` or `AIReviewFailed`
5. **No push mechanism** — frontend must poll `GET /review-status`

### 3. Fake LLM Boundary

#### Provider wiring

`LLM_PROVIDER=fake` selects `FakeLlmCompletionPort` via `backend/infrastructure/llm/factory.py:15-16`. No API key needed. This is also the **default** when no env var is set.

#### Determinism — fully deterministic

The fake provider computes everything from input content with zero randomness:

**Score heuristic** (`backend/infrastructure/llm/fake_completion.py:69-77`):

| Section body word count | Score |
|-------------------------|-------|
| < 5 words | 2 |
| 5–14 words | 3 |
| 15–29 words | 4 |
| ≥ 30 words | 5 |

**Feedback**: always `"Fake review for {section} section."` (line 37).

**Annotations**:
- **Conciseness** on Context section only, when full document > 500 chars (lines 80-97)
- **Inconsistency** cross-section annotation fires whenever both `## Decision` and `## Status` headings exist (lines 100-110) — always true for well-formed ADRs

No simulated latency — returns immediately.

#### Predicted output for `complete.md` fixture

Using `backend/tests/review_quality/fixtures/complete.md` as test content:

| Section | Word count | Score | Feedback |
|---------|-----------|-------|----------|
| Context | ~9 | 3 | "Fake review for Context section." |
| Options | ~2 | 2 | "Fake review for Options section." |
| Decision | ~5 | 3 | "Fake review for Decision section." |
| Status | ~1 | 2 | "Fake review for Status section." |
| Consequences | ~6 | 3 | "Fake review for Consequences section." |

Annotations: 1 cross-section inconsistency ("Status may not reflect the recorded decision.", location `## Status`). No conciseness annotation (document under 500 chars).

#### E2E assertion strategy

Tests **can assert exact scores and feedback text** — only timestamps (`reviewed_at`) and UUIDs (`id`, `source_event_id`) need fuzzy matching.

#### Available fixtures

`backend/tests/review_quality/fixtures/`:

| Fixture | Use case |
|---------|----------|
| `complete.md` | Happy-path: all 5 sections present |
| `missing_context.md` | Static `missing_section` detection |
| `empty_decision.md` | Placeholder/empty detection |
| `placeholder_status.md` | "TBD" placeholder detection |
| `missing_multiple_sections.md` | Multi-gap scenario |
| `extra_sections.md` | Tolerance of extra sections |

All are pure markdown, directly usable as ADR content in e2e tests.

### 4. E2E Infrastructure — What Exists vs What's Missing

#### EXISTS: Solid foundation

| Component | File(s) | Status |
|-----------|---------|--------|
| Playwright config | `frontend/playwright.config.ts` | Two webServer blocks (backend :8100, frontend :3100), auth project, chromium project |
| Auth setup | `frontend/e2e/auth.setup.ts` | Registers/logs in via API, stores sessionStorage state to `.auth/user.json` |
| Custom fixtures | `frontend/e2e/fixtures.ts` | Extends base `test` with sessionStorage injection for non-setup projects |
| AGENTS.md rules | `frontend/e2e/AGENTS.md` | Spec-writing conventions (risk-anchored, accessible locators, no waitForTimeout) |
| Browser install | `22-playwright-cli.sh` | Devcontainer hook: installs `playwright-cli`, browser binary, OS deps |
| Headed debugging | `.devcontainer/bin/start-display.sh` | Xvfb + x11vnc + noVNC at `localhost:6080` |
| CLI wrapper | `frontend/scripts/playwright-cli.sh` | Starts virtual display, delegates to `playwright-cli` |
| `.gitignore` entries | `frontend/.gitignore` | `.playwright-cli/` and `.auth/user.json` excluded |
| Package scripts | `frontend/package.json` | `e2e`, `e2e:auth`, `playwright:install`, `playwright:browser` |
| Port isolation | Config | Backend :8100 / frontend :3100 — no conflict with dev ports (3000/8000) |
| `reuseExistingServer` | Config | `!process.env.CI` — skips server start in local dev when already running |
| Playwright skills | `frontend/.agents/skills/playwright-cli/` | 11 reference docs for agent-driven spec generation |

#### MISSING: Gaps blocking north-star specs

| Gap | Impact | Severity |
|-----|--------|----------|
| **Zero spec files** | No actual tests to run; only `auth.setup.ts` and `fixtures.ts` exist in `e2e/` | Critical |
| **No seed spec** | AGENTS.md references `seed.spec.ts` as exemplar but it was deleted after failing (see below) | High |
| **No API test helpers** | No utility for creating ADRs with specific content via API (needed to set up review scenarios without walking through the full UI) | High |
| **No review-completion waiter** | No shared helper to poll `review-status` until `after_review`; each spec would reimplement | High |
| **No DB cleanup** | No mechanism to reset database between tests or ensure test isolation | Medium |
| **`playwright-report/` not gitignored** | 2 files committed (`index.html`, `data/*.md`) | Low |
| **`test-results/` not gitignored** | 2 files committed (`.last-run.json`, error context from failed seed spec) | Low |
| **No page object models** | No shared abstractions for common page interactions (login, create ADR, editor) | Medium |

#### Seed spec failure forensics

A `seed.spec.ts` was written and run but failed. The error context is preserved in `frontend/test-results/`:

**Test**: `seed.spec.ts >> E2E auth registration >> registering creates a session that survives a workspace reload`
**Error**: `expect(page).toHaveURL(/\/workspace$/)` — URL remained on `/register?email=...&password=...&confirmPassword=...` instead of navigating to `/workspace`.

**Root cause**: The form submission populated query params instead of posting — likely the registration form's `@submit` handler was not preventing default form behavior, or vee-validate's `handleSubmit` did not fire correctly in the e2e context. The form's `@submit="onSubmit"` binding on `register.vue` expects vee-validate interception, but the click may have triggered native form submission first, encoding fields as query params.

**Implication for Phase 3**: Auth registration through the UI works via `auth.setup.ts` (which uses Playwright's `request` API, not the form), so north-star specs that rely on `storageState` are not affected. However, a dedicated auth-flow spec testing UI registration will need to address this form submission issue.

## Code References

### Frontend flow
- `frontend/app/pages/login.vue:32-38` — Login form submit → `auth.login()` → navigate
- `frontend/app/pages/workspace/index.vue:63-84` — Create ADR form
- `frontend/app/pages/workspace/adr/[id].vue:166-206` — Submit for review + publish handlers
- `frontend/app/composables/useAdrReviewPolling.ts:63-68` — Poll → `after_review` → full reload
- `frontend/app/components/adr/AdrReviewAnnotations.vue:141-158` — Section ratings display
- `frontend/app/components/adr/AdrStatusBadge.vue:8-30` — Status → label/color mapping
- `frontend/composables/useApi.ts:96-106` — Bearer token injection
- `frontend/app/middleware/auth.ts:8-12` — Route guard

### Backend API
- `backend/infrastructure/api/routers/adr.py:68-324` — All ADR routes
- `backend/infrastructure/api/routers/auth.py:42-126` — Auth routes
- `backend/infrastructure/api/schemas/adr.py:71-81` — `AdrResponse` schema
- `backend/domain/adr/value_objects.py:10-15` — Status enum
- `backend/domain/adr/value_objects.py:69-91` — `SectionRating` model

### Fake LLM
- `backend/infrastructure/config.py:12-24` — `LlmProviderMode` + `Settings`
- `backend/infrastructure/llm/factory.py:14-50` — Provider factory
- `backend/infrastructure/llm/fake_completion.py:30-110` — Deterministic fake implementation
- `backend/application/services/adr_review_service.py:98-120` — Review pipeline merge + validate

### E2E infrastructure
- `frontend/playwright.config.ts:1-49` — Full Playwright config
- `frontend/e2e/auth.setup.ts:1-63` — Auth setup project
- `frontend/e2e/fixtures.ts:1-40` — Custom test fixtures with sessionStorage
- `frontend/scripts/playwright-cli.sh:1-14` — CLI wrapper for headed mode
- `.devcontainer/post-create.d/22-playwright-cli.sh:1-32` — Browser install automation

## Architecture Insights

1. **No push mechanism for review completion.** The frontend relies on 3-second polling (`useAdrReviewPolling`). In e2e tests, this means specs must wait for the poll cycle to detect `after_review` — not instant. With the fake LLM returning immediately, the first poll (3s after submit) should find the review complete, but tests must use a robust wait pattern (e.g., `page.waitForResponse` on the review-status endpoint or assert on visible review content).

2. **Auth uses sessionStorage, not cookies.** Playwright's built-in `storageState` only persists cookies and localStorage. The existing `fixtures.ts` works around this by injecting sessionStorage via `context.addInitScript`. This is a custom pattern that spec authors must understand — using raw `storageState` without the custom fixture will fail auth.

3. **Beacon save uses `keepalive` fetch.** The `useAdrPersistence` composable sends a `POST /save` with `keepalive: true` on `pagehide`/`visibilitychange`. This is not interceptable by standard Playwright route mocking, but since the test plan says "keep the API real" this is not a problem — the real backend handles it.

4. **ADR content template.** New ADRs are created with a starter template (`backend/domain/adr/template.py`). For the north-star e2e test, the spec would need to **replace** this content with a fixture like `complete.md` to get all 5 sections rated. The `PATCH` endpoint or editor blur-save can be used for this.

5. **Title uniqueness.** Per-user case-insensitive unique titles are enforced at DB level. E2e tests must use unique titles (e.g., timestamped) to avoid 409 conflicts across runs.

## Historical Context (from prior changes)

- `context/changes/testing-critical-path-api-integration/research.md` — Phase 1 research; established IDOR denial and persistence round-trip patterns
- `context/changes/testing-ai-review-contract-error-recovery/research.md` — Phase 2 research; fake LLM injection patterns, `_drain_event_bus` helpers, `_wait_for_review_status` utility at pytest level
- `context/changes/test-plan-refresh-2026-07-05/research.md` — Test plan refresh that reset Phase 3 scope after product pivot to LLM ratings

## Related Research

- `context/changes/testing-critical-path-api-integration/research.md` — Phase 1 patterns
- `context/changes/testing-ai-review-contract-error-recovery/research.md` — Phase 2 patterns
- `context/archive/2026-06-16-draft-authoring-persistence/research.md` — Persistence + beacon save design
- `context/archive/2026-07-05-after-review-status/research.md` — `after_review` status flow

## Open Questions

1. **Seed spec form submission bug**: The deleted `seed.spec.ts` failed because UI registration submitted form params as query string instead of calling `handleSubmit`. Is this a real product bug in `register.vue` or a test timing issue? Since `auth.setup.ts` bypasses the form (uses `request.post`), this may be a latent UI defect. Needs investigation before writing a UI-driven auth registration spec.

2. **DB cleanup between tests**: The test plan says "use unique test data and clean up records created by the test whenever the product exposes a cleanup path." Currently the only cleanup path is `DELETE /api/adrs/{id}` (soft delete). There is no user deletion endpoint. For CI parallel workers, this could cause cross-run pollution. Options: (a) unique emails per run, (b) DB reset between runs, (c) accept soft-isolation via unique data.

3. **Review polling timeout in e2e**: With the fake LLM returning instantly, the 3-second poll interval means ~3s delay before the frontend detects `after_review`. Should specs wait for the poll response, or intercept/accelerate polling? The AGENTS.md rule "Never use `page.waitForTimeout()`" means tests must wait for observable UI state (e.g., the review sidebar becoming visible).

4. **`playwright-report/` and `test-results/` cleanup**: These directories contain committed artifacts from the failed seed spec run. Should they be gitignored and the committed files removed?

5. **ADR content injection strategy**: The north-star spec needs a well-formed 5-section ADR. Two approaches: (a) type content through the markdown editor (slow, brittle), or (b) PATCH via API after creation (fast, deterministic). Option (b) aligns with AGENTS.md guidance to "keep auth, routing, the API, and the database real" — the editor is not what's under test for the review flow.
