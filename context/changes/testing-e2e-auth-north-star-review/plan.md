# E2E Auth + North-Star Review Implementation Plan

## Overview

Phase 3 of the test plan: prove the north-star review flow and auth login in a real browser with `LLM_PROVIDER=fake`. Two separate E2E specs backed by shared API helpers — one for auth login via the UI, one for the full create → review → publish journey. Infrastructure cleanup (gitignore, form fix, helpers) lands first.

## Current State Analysis

Playwright infrastructure is in place: config with dual webServer (backend :8100 / frontend :3100), `auth.setup.ts` registering via API and persisting sessionStorage to `.auth/user.json`, custom `fixtures.ts` injecting sessionStorage into browser contexts, and `e2e/AGENTS.md` defining spec conventions. The backend webServer already runs with `LLM_PROVIDER=fake`, selecting `FakeLlmCompletionPort` — a fully deterministic provider that scores sections by word count and produces fixed feedback text.

Zero spec files exist. Only `auth.setup.ts` and `fixtures.ts` are in `e2e/`. A `seed.spec.ts` was written and deleted after failing on form submission (native GET instead of SPA navigation). Committed artifacts from that failed run remain in `playwright-report/` and `test-results/`, neither of which is gitignored.

### Key Discoveries:

- `login.vue` uses `@submit="onSubmit"` without `.prevent` — same pattern that caused the seed spec failure on `register.vue`. The workspace form uses `@submit.prevent="onSubmit"` and works correctly. Login needs the `.prevent` fix before the auth spec can rely on form submission. (`frontend/app/pages/login.vue:61`)
- The fake LLM output for `complete.md` is fully predictable: Context 3/5, Options 2/5, Decision 3/5, Status 2/5, Consequences 3/5, plus 1 inconsistency annotation. Specs can assert exact scores and feedback text. (`backend/infrastructure/llm/fake_completion.py:69-77`)
- The review sidebar uses `aria-label="Review feedback"` on an `<aside>` element and auto-opens on `after_review` transition — a clear wait target for Playwright. (`frontend/app/components/adr/AdrReviewSidebar.vue:27-31`)
- Auth uses `sessionStorage` (key `adr-flow.access_token`), not cookies. Playwright's `storageState` only persists cookies/localStorage — the custom fixture in `fixtures.ts` works around this via `context.addInitScript`. API test helpers must read the token from `.auth/user.json` and add the `Authorization` header manually. (`frontend/e2e/fixtures.ts:29-33`)
- The frontend polls `GET /review-status` every 3 seconds (`useAdrReviewPolling.ts:63-68`). With the fake LLM returning instantly plus event-bus dispatch, the review sidebar should appear within one poll cycle (~3-5s after submit).

## Desired End State

Two passing E2E specs running via `pnpm run e2e`:

1. **Auth login spec** — proves a user can sign in via the login form and reach the workspace. Runs without `storageState` to test the actual login flow.
2. **North-star review spec** — proves the full journey: create ADR → inject reviewable content via API → submit for review → review sidebar appears with 5 section ratings and annotations → edit after review → publish as proposed. Uses `storageState` for authentication and API helpers for data setup.

Both specs follow `e2e/AGENTS.md` conventions: risk-anchored, accessible locators, no `waitForTimeout`, one test per file. `playwright-report/` and `test-results/` are gitignored. Shared API helpers (`e2e/helpers.ts`) are available for future specs.

Verification: `pnpm run e2e` exits 0 with both specs green. Manual verification via headed mode (`pnpm run playwright -- test`) shows the flows visually.

## What We're NOT Doing

- **Registration UI spec** — `register.vue` has a known form submission bug (`@submit` without `.prevent`). Documented in `AGENTS.md` known issues; fix deferred to a separate change.
- **Review-failed + retry E2E** — covered by Phase 2 integration tests at the API boundary. E2E would add cost without new signal.
- **Page object models** — premature with only 2 specs. Reconsider when spec count reaches 5+.
- **DB cleanup infrastructure** — unique ADR titles per test (`Date.now()` suffix) provide sufficient isolation without DB reset.
- **Route guard spec** — unauthenticated redirect to `/login` is a single middleware check, already covered by the login spec's prerequisite (navigating while unauthenticated).

## Implementation Approach

Three sequential phases: infrastructure first (gitignore, form fix, helpers), then the simpler auth spec, then the north-star spec that builds on both helpers and auth setup. Each phase is independently verifiable.

## Critical Implementation Details

**Timing & lifecycle** — The fake LLM returns instantly, but the frontend poll interval (3s) plus event-bus worker dispatch means ~3-5s between clicking "Publish for review" and the review sidebar appearing. Specs must wait for visible UI state (the sidebar landmark becoming visible), not a fixed timeout. Use `expect(...).toBeVisible({ timeout: 15_000 })` to accommodate CI variance.

**State sequencing** — ADR content must be PATCHed BEFORE submitting for review. The starter template has empty section bodies (0 words each → score 2 for all sections). The `complete.md` fixture has varying word counts that produce different scores — assertions depend on this content being in place before the review runs.

## Phase 1: Infrastructure Cleanup & Helpers

### Overview

Clean up committed E2E artifacts, fix the login form submission bug, create shared API test helpers, and update `AGENTS.md` conventions.

### Changes Required:

#### 1. Gitignore E2E artifacts

**File**: `frontend/.gitignore`

**Intent**: Prevent Playwright-generated reports and test results from being committed. These are ephemeral build outputs, not source.

**Contract**: Append `playwright-report/` and `test-results/` entries to the gitignore file.

#### 2. Remove committed artifacts from git tracking

**Intent**: Untrack the 4 files committed from the failed seed spec run across `frontend/playwright-report/` and `frontend/test-results/`.

**Contract**: `git rm -r --cached frontend/playwright-report/ frontend/test-results/` — removes from index without deleting local files.

#### 3. Fix login form submission

**File**: `frontend/app/pages/login.vue`

**Intent**: Prevent native form submission from racing with vee-validate's `handleSubmit` handler. The workspace create-ADR form already uses `@submit.prevent` and works correctly; login should follow the same pattern. Without this fix, Playwright's click may trigger a native GET submission (encoding fields as query params) instead of the SPA navigation.

**Contract**: Change `@submit="onSubmit"` to `@submit.prevent="onSubmit"` on the `<form>` element. Single attribute change; no logic change.

#### 4. Create API test helpers

**File**: `frontend/e2e/helpers.ts` (new)

**Intent**: Provide reusable API functions for E2E specs that need to set up test data without walking through the full UI. Keeps specs focused on the flow being tested rather than data setup mechanics.

**Contract**:
- `getAuthToken(): Promise<string>` — reads `.auth/user.json`, extracts the `adr-flow.access_token` value from the first origin's `sessionStorage` array. Throws if token is absent.
- `createAdr(request: APIRequestContext, title: string): Promise<{ id: string }>` — `POST /api/adrs` with Bearer token from `getAuthToken()`. Returns the created ADR's `id`. Throws on non-2xx.
- `seedAdrContent(request: APIRequestContext, id: string, content: string): Promise<void>` — `PATCH /api/adrs/{id}` with `{ content }` and Bearer token. Throws on non-2xx.
- `uniqueTitle(prefix: string): string` — returns `` `${prefix} ${Date.now()}` `` for test isolation across parallel runs.
- `COMPLETE_ADR_CONTENT: string` — inline constant matching `backend/tests/review_quality/fixtures/complete.md` content (all 5 sections with substantive body text).
- Imports `APIRequestContext` from `@playwright/test`. Uses relative path `'.auth/user.json'` consistent with existing `fixtures.ts`.

#### 5. Update E2E conventions

**File**: `frontend/e2e/AGENTS.md`

**Intent**: Remove stale reference to deleted `seed.spec.ts`, document the available helpers, and record the `register.vue` form submission bug as a known issue so future spec authors don't rediscover it.

**Contract**:
- Replace "Model new specs on `seed.spec.ts`." with guidance to use `auth-login.spec.ts` and `north-star-review.spec.ts` as models.
- Add a "Helpers" section describing `helpers.ts` exports.
- Add a "Known issues" section documenting the `register.vue` `@submit` bug (symptom: URL stays on `/register?email=...` instead of navigating to `/workspace`; workaround: auth.setup.ts uses API calls, not UI).

### Success Criteria:

#### Automated Verification:

- Gitignore effective: `git ls-files frontend/playwright-report frontend/test-results` returns empty
- TypeScript: `cd frontend && pnpm run typecheck` passes with `e2e/helpers.ts`
- Lint: `cd frontend && pnpm run lint` passes
- Existing tests unaffected: `cd frontend && pnpm run test` passes

#### Manual Verification:

- `AGENTS.md` reads clearly — stale reference gone, helpers and known issues documented
- Login form in browser still works after `.prevent` addition (manual click-through)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Auth Login E2E Spec

### Overview

Write the auth login E2E spec proving a user can sign in via the login form UI and land on the workspace page.

### Changes Required:

#### 1. Auth login spec

**File**: `frontend/e2e/auth-login.spec.ts` (new)

**Intent**: Prove that the login UI works end-to-end in a real browser. The auth setup project registers the user and stores credentials via API; this spec verifies the actual login page form flow. Imports `test` and `expect` from `@playwright/test` directly (not from `fixtures.ts`) and overrides `storageState` to start unauthenticated — the custom fixture's sessionStorage injection is not wanted here.

**Contract**:
- Risk anchor: test-plan.md §1 North Star ("Auth e2e is required alongside this north-star flow")
- Provenance: test-plan.md §3 Phase 3
- `test.use({ storageState: { cookies: [], origins: [] } })` at file level to override the chromium project's `storageState`
- Test steps:
  1. Navigate to `/login`
  2. Assert "Sign in" heading visible (`getByRole("heading", { name: "Sign in" })`)
  3. Fill email field (`getByLabel("Email")`) with `e2e@example.com`
  4. Fill password field (`getByLabel("Password")`) with `e2e-password-123`
  5. Click sign-in button (`getByRole("button", { name: "Sign in" })`)
  6. Assert URL matches `/workspace` (`toHaveURL(/\/workspace/)`)
  7. Assert workspace heading visible (`getByRole("heading", { name: "Workspace" })`)
- Credentials: same defaults as `auth.setup.ts` (env vars `E2E_USER_EMAIL` / `E2E_USER_PASSWORD` with fallbacks)

### Success Criteria:

#### Automated Verification:

- Spec passes: `cd frontend && pnpm run e2e -- auth-login.spec.ts` exits 0
- TypeScript: `cd frontend && pnpm run typecheck` passes
- Lint: `cd frontend && pnpm run lint` passes

#### Manual Verification:

- Spec runs visibly in headed mode: `pnpm run playwright -- test auth-login.spec.ts` shows the login form interaction
- No race conditions or flicker — form submits cleanly, navigation is immediate

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: North-Star Review E2E Spec

### Overview

Write the north-star E2E spec proving the full review journey: create ADR → inject content → submit for review → see ratings and annotations → edit → publish as proposed.

### Changes Required:

#### 1. North-star review spec

**File**: `frontend/e2e/north-star-review.spec.ts` (new)

**Intent**: Prove the complete north-star flow in a real browser — the test plan's definition of "it works." Uses `storageState` + custom fixtures for authentication. ADR content is injected via API PATCH (fast, deterministic) rather than typing through the editor. The fake LLM produces deterministic output that the spec asserts exactly.

**Contract**:
- Risk anchor: Risks #1 (garbage review output), #2 (stuck in_review), #4 (draft loss, frontend path) from test-plan.md §2
- Provenance: test-plan.md §1 North Star, §3 Phase 3
- Uses custom `test` and `expect` from `./fixtures` (authenticated via sessionStorage)
- Imports `createAdr`, `seedAdrContent`, `uniqueTitle`, `COMPLETE_ADR_CONTENT` from `./helpers`
- Test steps:
  1. **Setup via API**: `createAdr(request, uniqueTitle('E2E Review'))` → get `id`; `seedAdrContent(request, id, COMPLETE_ADR_CONTENT)`
  2. **Navigate**: `page.goto(\`/workspace/adr/${id}\`)`
  3. **Assert draft state**: "Draft" badge visible (`getByText("Draft")`); "Publish for review" button visible (`getByRole("button", { name: "Publish for review" })`)
  4. **Submit for review**: Click "Publish for review"
  5. **Assert in-review state**: "In review" badge visible; "This ADR is being reviewed" text visible
  6. **Wait for review completion**: `expect(page.getByRole('complementary', { name: 'Review feedback' })).toBeVisible({ timeout: 15_000 })` — waits for the review sidebar landmark to appear (auto-opens on `after_review`)
  7. **Assert after-review state**: "After review" badge visible; "Publish" button visible; "Edit based on review feedback" helper text visible
  8. **Assert section ratings**: Scope sidebar via `page.getByRole('complementary', { name: 'Review feedback' })`. Assert "Section ratings" heading visible. Assert all 5 section names present: Context, Options, Decision, Status, Consequences. Assert deterministic scores visible: at least one `3/5` and at least one `2/5` (matching fake LLM heuristic for `complete.md`)
  9. **Assert annotations**: "Inconsistency" heading visible within sidebar. Annotation message about status/decision inconsistency visible
  10. **Verify editor is editable**: Title input is enabled (`getByLabel("Title")` → `toBeEnabled()`); editor toolbar is visible (`locator('#adr-editor .md-editor-toolbar-wrapper')` → `toBeVisible()`)
  11. **Edit after review**: Clear title field and type a new title (e.g., append " — reviewed") to prove editing works in `after_review`; click outside the title field to trigger save-on-blur
  12. **Publish**: Click "Publish" button (`getByRole("button", { name: "Publish" })`)
  13. **Assert proposed state**: "Proposed" badge visible (`getByText("Proposed")`)

**Expected fake LLM output for `complete.md`** (used for deterministic assertions):

| Section | Words | Score | Feedback |
|---------|-------|-------|----------|
| Context | ~9 | 3 | "Fake review for Context section." |
| Options | ~2 | 2 | "Fake review for Options section." |
| Decision | ~5 | 3 | "Fake review for Decision section." |
| Status | ~1 | 2 | "Fake review for Status section." |
| Consequences | ~6 | 3 | "Fake review for Consequences section." |

Annotations: 1 inconsistency ("Status may not reflect the recorded decision.", location `## Status`). No conciseness annotation (document under 500 chars).

### Success Criteria:

#### Automated Verification:

- Spec passes: `cd frontend && pnpm run e2e -- north-star-review.spec.ts` exits 0
- Full suite passes: `cd frontend && pnpm run e2e` exits 0 (auth-login + north-star-review + auth.setup)
- TypeScript: `cd frontend && pnpm run typecheck` passes
- Lint: `cd frontend && pnpm run lint` passes

#### Manual Verification:

- Spec runs visibly in headed mode — full flow observable: login → create → editor → submit → polling indicator → review sidebar opens → ratings and annotations visible → publish → proposed badge
- Review sidebar appears naturally after one poll cycle (~3-5s), not instantaneously
- No console errors or unhandled promise rejections in the browser during the flow
- Publishing transitions cleanly — no double-click or stale state issues

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### E2E Tests (this plan):

- Auth login flow — form submission → workspace navigation
- North-star review — full create → review → publish journey with deterministic assertions

### Existing Coverage (not changed by this plan):

- **Backend integration (Phase 1)**: IDOR denial, persistence round-trips (`backend/tests/infrastructure/api/test_adr_api.py`)
- **Backend review contract (Phase 2)**: 5-rating contract, malformed LLM handling, failure → retry recovery (`backend/tests/application/handlers/test_run_ai_review.py`)
- **Frontend unit**: Auth store, ADR persistence, review UI components (`frontend/tests/`)

### What's NOT Tested E2E:

- Registration UI (known bug, deferred)
- Review failure + retry (covered by Phase 2 integration)
- Save-on-unload/beacon (browser API limitation — covered by frontend unit tests)
- ADR deletion/removal (not part of north-star flow)

## Performance Considerations

- The fake LLM returns instantly — no artificial latency. The 3s poll interval is the primary delay.
- API data setup (create + PATCH) is sub-100ms. Typing through the editor would add 5-10s per spec.
- Both specs are independent and can run in parallel (`fullyParallel: true` in Playwright config). Title uniqueness via `Date.now()` prevents conflicts.

## References

- Research: `context/changes/testing-e2e-auth-north-star-review/research.md`
- Test plan: `context/foundation/test-plan.md` §1 North Star, §3 Phase 3
- Phase 1 cookbook: `context/foundation/test-plan.md` §6 Phase 1
- Phase 2 cookbook: `context/foundation/test-plan.md` §6 Phase 2
- Playwright config: `frontend/playwright.config.ts`
- Auth setup: `frontend/e2e/auth.setup.ts`
- Custom fixtures: `frontend/e2e/fixtures.ts`
- Fake LLM: `backend/infrastructure/llm/fake_completion.py`
- Complete fixture: `backend/tests/review_quality/fixtures/complete.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Infrastructure Cleanup & Helpers

#### Automated

- [x] 1.1 Gitignore effective: `git ls-files frontend/playwright-report frontend/test-results` returns empty
- [x] 1.2 TypeScript passes with `e2e/helpers.ts`: `cd frontend && pnpm run typecheck`
- [x] 1.3 Lint passes: `cd frontend && pnpm run lint`
- [x] 1.4 Existing tests unaffected: `cd frontend && pnpm run test`

#### Manual

- [ ] 1.5 AGENTS.md reads clearly — stale reference gone, helpers and known issues documented
- [ ] 1.6 Login form still works after `.prevent` addition

### Phase 2: Auth Login E2E Spec

#### Automated

- [x] 2.1 Spec passes: `cd frontend && pnpm run e2e -- auth-login.spec.ts`
- [x] 2.2 TypeScript passes: `cd frontend && pnpm run typecheck`
- [x] 2.3 Lint passes: `cd frontend && pnpm run lint`

#### Manual

- [ ] 2.4 Spec runs visibly in headed mode — login form interaction is clean
- [ ] 2.5 No race conditions or flicker on form submission

### Phase 3: North-Star Review E2E Spec

#### Automated

- [ ] 3.1 Spec passes: `cd frontend && pnpm run e2e -- north-star-review.spec.ts`
- [ ] 3.2 Full suite passes: `cd frontend && pnpm run e2e`
- [ ] 3.3 TypeScript passes: `cd frontend && pnpm run typecheck`
- [ ] 3.4 Lint passes: `cd frontend && pnpm run lint`

#### Manual

- [ ] 3.5 Full flow observable in headed mode
- [ ] 3.6 Review sidebar appears after poll cycle (~3-5s)
- [ ] 3.7 No console errors during the flow
- [ ] 3.8 Publish transitions cleanly to "Proposed"
