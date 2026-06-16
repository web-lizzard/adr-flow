# Draft Authoring & Persistence — Plan Brief

> Full plan: `context/changes/draft-authoring-persistence/plan.md`
> Research: `context/changes/draft-authoring-persistence/research.md`

## What & Why

S-02 delivers the first real ADR behavior: users create a draft from the five-heading starter template, edit markdown in a CodeMirror editor, and have their work automatically saved on blur and tab close. This is the foundation every later slice (AI review, publish, history) depends on — without reliable draft persistence, the core product loop cannot function.

## Starting Point

F-02 delivered the `adrs` projection table, event store, and full ADR domain vocabulary (aggregate, six events, value objects). S-01 delivered JWT auth, the composition root, and the write-side UoW pattern (`RegisterUserCommandHandler`). The backend has all the persistence infrastructure and auth seams S-02 needs — but zero ADR behavior code. The frontend has auth pages and a protected workspace placeholder — but no ADR pages, editor, or save logic.

## Desired End State

A logged-in user enters a required title (validated for per-user uniqueness), clicks "Create", lands on an editor page with CodeMirror pre-filled with the starter template, edits markdown with syntax highlighting, sees their title editable inline above the editor, and has every edit automatically persisted when they click away or close the tab. Returning to the same URL — even after a full browser restart — recovers the latest saved content. Title changes are also validated for uniqueness via a search endpoint.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|---|---|---|---|
| Title on create | Required before creation | Ensures every ADR has a meaningful name from the start; validated for per-user uniqueness. | Plan |
| Markdown editor | CodeMirror 6 via `vue-codemirror6` | Syntax highlighting, undo/redo, line numbers out of the box; SSR-compatible Vue wrapper. | Plan |
| Title editing | Editable inline on editor page | Title and content save together on blur — simpler UX and single API call. | Plan |
| Save-on-unload transport | `navigator.sendBeacon` POST | Only reliable way to fire HTTP on tab close; falls back gracefully. | Plan |
| PATCH scope | Single PATCH with optional title + content | Avoids endpoint proliferation; partial updates are natural for a save-on-blur pattern. | Plan |
| `aggregate_type` casing | Lowercase `"adr"` for new events | Aligns with architecture doc; existing `"User"` normalized later. | Plan |
| Beacon endpoint | Dedicated `POST /api/adrs/{id}/save` | sendBeacon only supports POST; shares `UpdateAdrContentCommandHandler` with PATCH. | Research / Plan |
| Title uniqueness | Per-user, case-insensitive | Prevents confusion from duplicate names; enforced in handlers + validated in frontend via search. | Plan |
| Title search | `GET /api/adrs/search?q=...` (ILIKE) | Simple Python-backed lexical search for uniqueness validation and future list filtering. | Plan |

## Scope

**In scope:**
- Backend: starter template, AdrProjection/AdrRepository ports + SQL adapters (incl. title search), UoW extension, CreateAdr + UpdateAdrContent commands (with title uniqueness), GetAdr + SearchAdrsByTitle queries, ADR router (5 endpoints), schemas, bootstrap wiring, integration tests
- Frontend: CodeMirror packages, API client extensions (incl. search), ADR Pinia store, editor component, editor page, save composable (blur + unload), workspace "Create ADR" form with title uniqueness validation, store tests

**Out of scope:**
- ADR list/cards (S-03), AI review (S-04), publish (S-05), soft-delete (S-06)
- Continuous autosave, rich WYSIWYG, split preview
- Event dispatcher / startup replay

## Architecture / Approach

Full-stack vertical slice mirroring S-01 patterns. Backend: command handlers emit events and update projections in a UoW transaction; query handler reads from the projection table with ownership filter; router maps domain errors to HTTP status codes; bootstrap wires everything via constructor injection stored on `app.state`. Frontend: Pinia store manages editor state + API calls; CodeMirror component provides markdown editing; a persistence composable combines blur-save (`$fetch` PATCH) with unload-save (`sendBeacon` POST).

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Backend persistence infrastructure | Ports, adapters, UoW extension, domain errors, template constant | UoW extension must be additive — no regression on User writes |
| 2. Backend command + query handlers | CreateAdr, UpdateAdrContent, GetAdr | Ownership check and status guard correctness |
| 3. Backend API layer + integration tests | 5 endpoints (incl. search), schemas, bootstrap, full test coverage | Beacon endpoint auth via cookies (no custom headers) |
| 4. Frontend editor + save persistence | CodeMirror editor, save composable, workspace entry point, tests | sendBeacon reliability on tab close; CodeMirror SSR hydration |

**Prerequisites:** S-01 auth flow working (JWT cookies, protected routes, workspace page). F-02 `adrs` table migrated.
**Estimated effort:** ~2-3 sessions across 4 phases.

## Open Risks & Assumptions

- OS crash or force-kill may bypass `pagehide`/`visibilitychange` — sendBeacon won't fire. Accepted for MVP; escalate to debounced autosave if pilots find gaps.
- `sendBeacon` payload limit (~64 KiB) is assumed sufficient for ADR content. ADRs are typically 1-5 KB; monitor in production.
- `vue-codemirror6` SSR compatibility is documented but untested in this Nuxt 4 setup — `.client.vue` naming is the safety net.

## Success Criteria (Summary)

- User provides a required title (validated unique per user) and creates an ADR with the five-heading starter template
- Duplicate title is rejected with a clear error both in the UI and backend
- Content survives blur-save + page refresh (PATCH path)
- Content survives tab-close + URL reopen (sendBeacon path)
- Search endpoint returns matching ADRs by title for the authenticated user
