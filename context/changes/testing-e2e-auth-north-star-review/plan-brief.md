# E2E Auth + North-Star Review — Plan Brief

> Full plan: `context/changes/testing-e2e-auth-north-star-review/plan.md`
> Research: `context/changes/testing-e2e-auth-north-star-review/research.md`

## What & Why

Phase 3 of the test plan: prove that the north-star review flow and auth login work end-to-end in a real browser with the LLM mocked at the API boundary (`LLM_PROVIDER=fake`). This is the test plan's definition of "it works" — login → create ADR → submit for review → see section ratings and annotations → edit → publish as proposed. Without this, the product's core value proposition is unverified at the integration layer where users actually experience it.

## Starting Point

Playwright infrastructure exists and works: config with dual webServer, `auth.setup.ts` registering via API, custom `fixtures.ts` injecting sessionStorage (the app's auth token lives in sessionStorage, not cookies). Zero spec files have landed. The fake LLM is deterministic (scores sections by word count, fixed feedback text). Committed artifacts from a failed seed spec sit in `playwright-report/` and `test-results/`. Both `login.vue` and `register.vue` have a latent `@submit` bug (missing `.prevent`).

## Desired End State

Two passing E2E specs (`pnpm run e2e` exits 0): an auth login spec proving the login form works, and a north-star spec proving the full review journey with exact assertions against the fake LLM's deterministic output. Shared API helpers (`e2e/helpers.ts`) enable future specs to set up test data via API. `AGENTS.md` is updated and the `register.vue` bug is documented.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|----------|--------|-------------------|--------|
| Spec scope | Separate specs (auth + north-star) | Each has a distinct auth context and failure mode — separation keeps tests independent and debuggable. | Plan |
| Content injection | PATCH via API | Faster (sub-100ms vs 5-10s typing), deterministic, and the editor is not what's under test for the review flow. | Plan |
| Auth UI scope | Login only, document register bug | The register.vue form submission bug is known; fixing it is a separate change. Login is needed and fixable with `.prevent`. | Plan |
| Test isolation | Unique titles per test, shared user | `Date.now()` suffix prevents title conflicts; DB reset adds infra cost for no added signal at 2 specs. | Plan |
| Review wait pattern | Wait for visible UI state | Aligns with AGENTS.md ("never waitForTimeout"); the sidebar's `aria-label="Review feedback"` is a clear landmark. | Plan / Research |
| Gitignore cleanup | Phase 1 of this plan | Quick prerequisite — prevents committing future artifacts before specs start generating them. | Plan |

## Scope

**In scope:**
- Gitignore + remove committed `playwright-report/` and `test-results/`
- Fix `login.vue` `@submit` → `@submit.prevent`
- API test helpers (`getAuthToken`, `createAdr`, `seedAdrContent`, `uniqueTitle`, `COMPLETE_ADR_CONTENT`)
- `AGENTS.md` update (stale ref, helpers, known issues)
- Auth login E2E spec (form → workspace)
- North-star review E2E spec (create → PATCH → submit → ratings → edit → publish)

**Out of scope:**
- Registration UI spec (known form bug)
- Review-failed + retry E2E (Phase 2 integration covers this)
- Page object models (premature at 2 specs)
- DB cleanup infrastructure (unique titles suffice)

## Architecture / Approach

Both specs run in Playwright's "chromium" project, which depends on the "setup" project (user registration via API). The north-star spec uses `storageState` + custom fixtures for authentication; the auth login spec overrides `storageState` with empty state to test the actual form flow. API helpers read the auth token from `.auth/user.json` and add Bearer headers manually — necessary because the app uses sessionStorage (not cookies) for auth. The backend's fake LLM (`LLM_PROVIDER=fake`) produces deterministic scores based on section word counts, enabling exact assertions on ratings and annotations.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|-------|-----------------|----------|
| 1. Infrastructure cleanup & helpers | Gitignore, login fix, API helpers, AGENTS.md update | Login `.prevent` fix might not resolve the form submission issue if root cause is elsewhere |
| 2. Auth login E2E spec | `auth-login.spec.ts` — login form → workspace | Flaky on slow CI if form submission has timing sensitivity |
| 3. North-star review E2E spec | `north-star-review.spec.ts` — full create → review → publish | Review sidebar wait may need timeout tuning; poll interval (3s) + event-bus dispatch timing |

**Prerequisites:** Phase 1 and 2 of the test plan are complete (API integration + review contract tests). Playwright browser is installed (`22-playwright-cli.sh`).
**Estimated effort:** ~1-2 sessions across 3 phases.

## Open Risks & Assumptions

- The `login.vue` `@submit` fix (adding `.prevent`) is assumed to resolve the form submission issue. If vee-validate's `handleSubmit` is the root cause, a deeper investigation is needed.
- The event-bus worker dispatch timing is assumed to be < 1s with the fake LLM. If the worker poll interval is longer, the 15s timeout may need adjustment.
- `register.vue` has the same `@submit` bug — documented but not fixed. A future registration UI spec will need this addressed first.

## Success Criteria (Summary)

- `pnpm run e2e` exits 0 with both specs green (auth login + north-star review)
- The north-star spec asserts 5 section ratings with deterministic scores and at least 1 annotation — proving the review pipeline delivers actionable feedback to the user
- Both specs run reliably in headed mode for visual verification
