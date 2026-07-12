# E2E Testing Rules

- Start each spec from a named risk in `context/foundation/test-plan.md`.
- Model new specs on `auth-login.spec.ts` and `north-star-review.spec.ts`.
- Use `getByRole`, `getByLabel`, and `getByText` as primary locators. Fall
  back to `getByTestId` only when accessible attributes are ambiguous.
- Never use CSS selectors, XPath, or DOM structure to locate elements.
- Keep every test independently runnable. Use unique test data and clean up
  records created by the test whenever the product exposes a cleanup path.
- Never use `page.waitForTimeout()`. Wait for a URL, response, or visible
  application state.
- Assert an observable business outcome that would fail if the named risk
  materialized.
- Use storage state for authenticated scenarios. Only auth-focused specs may
  exercise registration or login through the UI.
- Keep auth, routing, the API, and the database real. The Playwright backend
  runs with `LLM_PROVIDER=fake`; do not mock internal application endpoints.
- Put one test in each spec file. Include risk and seed provenance at the top,
  and comment the plan step before the actions that implement it.

## Helpers

`e2e/helpers.ts` provides API utilities for authenticated data setup:

- `getAuthToken()` — reads `.auth/user.json` and returns the `adr-flow.access_token` from sessionStorage.
- `createAdr(request, title)` — `POST /api/adrs` with Bearer auth; returns `{ id }`.
- `seedAdrContent(request, id, content)` — `PATCH /api/adrs/{id}` with Bearer auth.
- `uniqueTitle(prefix)` — returns a timestamp-suffixed title for test isolation.
- `COMPLETE_ADR_CONTENT` — fixture content matching `backend/tests/review_quality/fixtures/complete.md` for deterministic fake-LLM review output.

## Known issues

- **`register.vue` form submission** — uses `@submit` without `.prevent`, so a native GET submission can race with vee-validate's `handleSubmit`. Symptom: URL stays on `/register?email=...` instead of navigating to `/workspace`. Workaround: `auth.setup.ts` registers via API, not the registration UI. Fix deferred to a separate change.
