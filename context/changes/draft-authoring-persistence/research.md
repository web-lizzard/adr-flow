---
date: 2026-06-16T14:00:00+00:00
researcher: Cursor
git_commit: unavailable
branch: adr-flow-s02
repository: adr-flow
topic: "Create and save ADR drafts from the starter template (S-02 draft-authoring-persistence)"
tags: [research, codebase, draft-authoring, adr, persistence, s-02, frontend, backend]
status: complete
last_updated: 2026-06-16
last_updated_by: Cursor
---

# Research: Create and save ADR drafts from the starter template (S-02)

**Date**: 2026-06-16T14:00:00+00:00
**Researcher**: Cursor
**Git Commit**: unavailable (worktree `gitdir` not mounted in this environment)
**Branch**: adr-flow-s02
**Repository**: adr-flow

## Research Question

What exists in the codebase today for roadmap slice **S-02 (`draft-authoring-persistence`)** — create an ADR from the starter template, edit markdown, and recover saved draft content after leaving or refreshing — and what must be built to satisfy FR-004, FR-005, FR-006, and NFR: No draft loss?

## Summary

**S-02 is not started.** Prerequisites are largely in place:

- **F-02 (`persistence-scaffold`)** — **implemented**: `events`, `users`, and `adrs` tables; ADR domain vocabulary (aggregate, value objects, six events including `ADRContentUpdated`); Alembic migrations; event store and user projection adapters.
- **S-01 (`account-access`)** — **mostly implemented**: JWT httpOnly cookie auth, register/login/me API, protected `/workspace` placeholder, Pinia auth store, route middleware. Phase 5 backend unit-test checklist is still open; change status is `implementing`.

**All vertical-slice work for S-02 remains greenfield:**

| Layer | Status |
|-------|--------|
| Backend commands (`CreateAdr`, `UpdateAdrContent`) | Missing |
| ADR projection port/adapter + UoW extension | Missing |
| ADR read repository + `GetAdr` query | Missing |
| ADR API router + schemas | Missing |
| Starter template constant | Missing (PRD/docs only) |
| Frontend ADR routes, editor, save hooks | Missing |
| ADR integration tests | Missing |

S-02 should follow the established `RegisterUserCommandHandler` pattern: command → domain event → event store append + projection write in one UoW transaction; protected routes use `get_current_user_id`; ownership enforced in handlers via `user_id` filtering.

Recommended MVP shape: `POST /api/adrs` (create with starter template), `GET /api/adrs/{id}` (reload draft), `PATCH /api/adrs/{id}` (content save); frontend route `workspace/adr/[id].vue` with a plain markdown textarea (no heavy editor dependency required for MVP), save-on-blur + `beforeunload` persistence via `@vueuse/core`.

## Detailed Findings

### Product requirements (S-02 scope)

From `context/foundation/roadmap.md` and `context/foundation/prd.md`:

| Ref | Requirement |
|-----|-------------|
| **Outcome** | User creates an ADR from the starter template, edits markdown, and recovers saved draft content after leaving or refreshing |
| **FR-004** | Starter template pre-fills five H2 headings: `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences` |
| **FR-005** | Edit markdown in any status except `in_review` (S-02 exercises `draft` only) |
| **FR-006** | Persist on save-on-blur and save-on-unload (no continuous debounced autosave) |
| **NFR** | No draft loss on browser close, refresh, or session expiry |

**Starter template** (canonical headings; body content under each section is author-filled):

```markdown
## Context

## Options

## Decision

## Status

## Consequences
```

No multi-line template constant exists in code yet. Test fixtures use partial strings like `"## Context\n\nTBD"` in `backend/tests/domain/test_adr.py`.

**Note:** `context/changes/github-issues/S-02-draft-authoring-persistence.md` is cited in prior research but **does not exist on disk**. Requirements are reconstructed from PRD, roadmap, and `persistence-scaffold/research.md`.

### Backend — what exists (F-02 + S-01 foundations)

#### ADR domain vocabulary (behavior-free until S-02)

Frozen dataclass aggregate with all fields needed for the lifecycle:

```14:25:backend/domain/adr/aggregate.py
@dataclass(frozen=True, slots=True)
class ADR:
    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent
    status: AdrStatus
    review_result: ReviewResult | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
```

Six domain events defined, including S-02 events:

```6:15:backend/domain/adr/events.py
class ADRCreated(DomainEvent):
    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent

class ADRContentUpdated(DomainEvent):
    adr_id: AdrId
    content: AdrContent
```

`AdrStatus` enum: `draft | in_review | after_review | proposed` (`backend/domain/adr/value_objects.py`).

F-02 explicitly keeps aggregates behavior-free until slices add logic (`backend/tests/domain/test_vocabulary_only.py`).

#### Persistence schema

`adrs` projection table exists with `user_id`, `title`, `content` (markdown text), `status`, `review_annotations` JSONB (null until S-04), `is_deleted`, timestamps, and `ix_adrs_user_id` index (`backend/infrastructure/adapters/persistence/models.py`, migration `001_initial_events_users_adrs.py`).

#### Auth seam (S-01 — reuse for S-02)

`get_current_user_id` dependency reads JWT from httpOnly `session` cookie and returns authenticated `UUID` or 401 (`backend/infrastructure/api/dependencies.py:36-48`).

Auth router pattern to copy for ADR routes:

```101:111:backend/infrastructure/api/routers/auth.py
@router.get("/me", response_model=UserResponse)
async def me(
    user_id: UUID = Depends(get_current_user_id),
    handler: GetCurrentUserQueryHandler = Depends(get_current_user_handler),
) -> UserResponse:
```

#### Write-side pattern to copy

`RegisterUserCommandHandler` shows the UoW transaction pattern S-02 must follow:

```44:67:backend/application/commands/register_user.py
        async with self._uow_factory.begin() as uow:
            user_id = uuid4()
            // ...
            await uow.event_store.append(
                [event],
                aggregate_id=user_id,
                aggregate_type="User",
            )
            await uow.user_projection.insert(
                user_id=user_id,
                email=email.value,
                password_hash=password_hash,
                created_at=occurred_at,
            )
            return user_id
```

**Minor inconsistency to resolve in S-02:** `aggregate_type="User"` uses PascalCase; architecture doc specifies lowercase `user`/`adr`. Align when implementing ADR commands.

#### UoW gap

Current `UnitOfWork` port exposes only `event_store` + `user_projection` — no `adr_projection`:

```8:10:backend/application/ports/unit_of_work.py
class UnitOfWork(Protocol):
    event_store: EventStore
    user_projection: UserProjection
```

`SqlUnitOfWorkFactory` mirrors this (`backend/infrastructure/adapters/persistence/unit_of_work.py:43-50`).

### Backend — what S-02 must add

Per `context/foundation/application-architecture.md:184-185`:

| Artifact | Purpose |
|----------|---------|
| `domain/adr/template.py` (or similar) | `ADR_STARTER_TEMPLATE` constant |
| `application/commands/create_adr.py` | `CreateAdr` → `ADRCreated` (status `draft`, starter content) |
| `application/commands/update_adr_content.py` | `UpdateAdrContent` → `ADRContentUpdated` |
| `application/queries/get_adr.py` | Load ADR for editor reload |
| `application/ports/adr_projection.py` | Insert/update projection port |
| `application/ports/adr_repository.py` | Read-side port with ownership filter |
| `infrastructure/adapters/persistence/projections/adr_projection.py` | SQL insert/update adapter |
| `infrastructure/adapters/persistence/repositories/adr_repository.py` | SQL read adapter |
| `infrastructure/api/routers/adr.py` | HTTP endpoints |
| `infrastructure/api/schemas/adr.py` | Request/response models |
| `domain/errors.py` extensions | `AdrNotFound`, access denied |
| `infrastructure/bootstrap.py` | Wire handlers, mount ADR router |

**Suggested REST API** (not documented in-repo; design in `/plan`):

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/api/adrs` | Create draft; seed starter template; return `adr_id` |
| `GET` | `/api/adrs/{id}` | Fetch ADR for authenticated owner |
| `PATCH` | `/api/adrs/{id}` | Update `content` (and optionally `title`); emit `ADRContentUpdated` |

**Domain rules for S-02:**

- `CreateAdr` sets status `draft`, content = starter template, `user_id` = caller.
- `UpdateAdrContent` only when status ≠ `in_review` (FR-005); S-02 only creates/edits `draft`.
- Commands validate `adr.user_id == command.user_id`; queries filter `WHERE user_id = :caller AND is_deleted = false`.
- Routers never `UPDATE adrs` directly — only through command handlers.

**Out of S-02 scope:** `ADRSubmittedForReview`, AI review, publish, soft-delete, ADR list/cards (S-03), event dispatcher/startup replay.

### Frontend — what exists (S-01 shell)

| Route | File | Middleware | Status |
|-------|------|------------|--------|
| `/` | `frontend/app/pages/index.vue` | — | Redirect to workspace or login |
| `/login`, `/register` | `login.vue`, `register.vue` | `guest` | Working |
| `/workspace` | `frontend/app/pages/workspace/index.vue` | `auth` | Protected placeholder |

Workspace explicitly defers S-02:

```19:31:frontend/app/pages/workspace/index.vue
    <Card>
      <CardHeader>
        <CardTitle>Your ADRs</CardTitle>
        <CardDescription>
          Architecture Decision Records will appear here in a future release.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p class="text-sm text-muted-foreground">
          This is your protected landing page. Start documenting decisions once
          the ADR list ships in S-02.
        </p>
      </CardContent>
    </Card>
```

**API client:** `frontend/composables/useApi.ts` has only `fetchHealth()` and `apiPath()`. Auth store uses `$fetch` + `apiPath("/auth/me")` pattern (`frontend/app/stores/auth.ts`).

**Nitro proxy:** same-origin `/api/*` → FastAPI backend (`frontend/server/routes/api/[...path].ts`).

**No markdown editor dependency** in `frontend/package.json` (no CodeMirror, Monaco, TipTap, etc.). shadcn-vue primitives exist (Button, Card, Input, Form) but **no Textarea** component yet.

**No save-on-blur/unload patterns** anywhere in frontend — zero `beforeunload`, `visibilitychange`, or persistence composables.

### Frontend — what S-02 must add

| Artifact | Purpose |
|----------|---------|
| `frontend/app/pages/workspace/adr/[id].vue` | Protected editor page (`middleware: ["auth"]`) |
| `frontend/app/components/adr/AdrMarkdownEditor.vue` | Markdown textarea + blur handler |
| `frontend/app/composables/useAdrPersistence.ts` | Save-on-blur + `beforeunload` via `@vueuse/core` |
| `frontend/app/stores/adr.ts` + `useAdr.ts` | Load/create/save state (mirror auth store pattern) |
| `frontend/composables/useApi.ts` extensions | `createAdr`, `fetchAdr`, `updateAdrContent` |
| `frontend/app/pages/workspace/index.vue` update | "Create ADR" button → create → navigate to editor |

**Persistence strategy (FR-006):**

1. **Save-on-blur** — `@blur` on editor fires `PATCH` if content is dirty.
2. **Save-on-unload** — `beforeunload` + optionally `visibilitychange` fires save; consider `fetch` with `keepalive: true` or `navigator.sendBeacon` for reliability on tab close.
3. **No continuous autosave** — per PRD/roadmap speed decision.

**Editor choice for MVP:** A shadcn Textarea or native `<textarea>` with monospace styling is sufficient for S-02. Rich WYSIWYG or split preview can wait. `@vueuse/core` is already a dependency.

**Unload edge case (open question):** OS crash or force-kill may bypass `beforeunload`. Roadmap and PRD flag this as a verification risk, not a blocker for MVP.

### Test strategy

`context/foundation/test-plan.md` Phase 3, risk #4 (High):

- Backend integration: save endpoint persists content correctly.
- Frontend integration: blur/unload events actually fire API calls.
- Anti-pattern: testing API alone without verifying browser triggers.

Existing frontend test pattern: mock `apiPath` + `$fetch` in `frontend/tests/auth.store.test.ts`.

Backend auth integration tests in `backend/tests/infrastructure/api/test_auth.py` (30+ cases) provide the template for ADR API tests.

## Code References

- `backend/domain/adr/aggregate.py:14-25` — ADR aggregate dataclass (vocabulary only)
- `backend/domain/adr/events.py:6-32` — All six ADR domain events including S-02 events
- `backend/domain/adr/value_objects.py` — `AdrStatus`, `AdrContent`, `AdrTitle`
- `backend/infrastructure/adapters/persistence/models.py:48-70` — `adrs` ORM model
- `backend/application/commands/register_user.py:44-67` — UoW write pattern to copy
- `backend/infrastructure/api/dependencies.py:36-48` — `get_current_user_id` for protected ADR routes
- `backend/application/ports/unit_of_work.py:8-10` — UoW port to extend with `adr_projection`
- `frontend/app/pages/workspace/index.vue:19-31` — Workspace placeholder awaiting S-02
- `frontend/composables/useApi.ts:5-14` — API path helper to extend
- `frontend/app/stores/auth.ts:29-67` — Pinia + `$fetch` pattern for ADR store
- `frontend/app/middleware/auth.ts:1-10` — Protected route middleware
- `context/foundation/application-architecture.md:104-110` — Ownership enforcement seam
- `context/foundation/application-architecture.md:184-185` — S-02 module additions

## Architecture Insights

1. **Prerequisites are ready; S-02 is the first ADR behavior slice.** F-02 delivered schema and vocabulary; S-01 delivered auth. S-02 adds the first real ADR writes and the first feature UI beyond auth forms.

2. **Follow the register-user vertical slice.** One command file per use case, handler takes ports via `__init__`, single `handle()` method, UoW wraps event append + projection in one transaction.

3. **Ownership in handlers, not routers.** Pass `user_id` from `get_current_user_id` into commands/queries; validate before load/write. This seam extends to workspaces post-MVP without rewriting ADR routes.

4. **`ADRContentUpdated` exists in code but not in architecture doc event list** (`application-architecture.md:118`). Event is implemented; doc update is a chore item, not a blocker.

5. **Starter template belongs in backend domain** (single source of truth for `CreateAdr`); frontend can duplicate for optimistic display or rely on API response after create.

6. **Keep S-02 narrow.** No ADR list (S-03), no review submit (S-04), no publish (S-05). Minimum viable flow: workspace "Create ADR" → editor → save → refresh recovers content.

7. **S-01 closure is soft prerequisite.** Backend auth and protected workspace work today; Phase 5 unit tests and formal `implemented` status are still open but should not block S-02 planning.

## Historical Context (from prior changes)

- `context/changes/persistence-scaffold/research.md` — Richest prior ADR domain model research; defines `CreateAdr`/`UpdateAdrContent` events, starter template headings, embed-annotations decision, state machine.
- `context/changes/persistence-scaffold/change.md` — F-02 status `implemented`.
- `context/changes/account-access/plan.md` — S-01 full spec; Phases 1–4 done, Phase 5 backend unit tests pending (lines 691–698).
- `context/changes/account-access/change.md` — S-01 status `implementing`.
- `context/archive/2026-06-15-testing-critical-path-domain-auth/` — Auth hardening tests; notes ADR endpoints will reuse `get_current_user_id`.
- `context/foundation/roadmap.md:111-113` — S-02 risk: save-on-blur + save-on-unload simplicity under `speed` goal.
- `context/foundation/test-plan.md:57` — Phase 3 draft-loss test depends on S-02 implementation.

## Related Research

- `context/changes/persistence-scaffold/research.md` — Domain aggregates, F-02 schema implications, annotation embed model
- `context/changes/account-access/plan.md` — Auth API, workspace placeholder, composition root patterns

## Open Questions

1. **Does save-on-blur + save-on-unload suffice against draft loss?** — Roadmap/PRD open question. OS crash may bypass unload. Verify in QA; escalate to debounced autosave only if pilots find gaps. Owner: user.

2. **Exact REST paths and request shapes** — Not documented in-repo. Confirm in `/plan` (recommendation above: `POST/GET/PATCH /api/adrs`).

3. **Is `proposed` literally editable?** — FR-005 permits editing in any status except `in_review`; slices only exercise `draft` and `after_review`. S-02 can restrict to `draft` only. Owner: user.

4. **Title handling on create** — PRD emphasizes content template; default title strategy (e.g. "Untitled ADR" or prompt) not specified. Decide in plan.

5. **Markdown editor dependency** — Plain textarea vs lightweight library (e.g. CodeMirror for syntax). MVP favors textarea for speed; preview pane is optional.

6. **`aggregate_type` casing** — Existing auth uses `"User"`; architecture specifies lowercase. Align in S-02 or defer global normalization.

7. **S-01 formal closure** — Should S-02 wait for Phase 5 unit tests and `account-access` → `implemented`, or proceed in parallel? Roadmap says "Requires S-01"; functional dependency is met.

## Recommended `/plan` work breakdown

### Backend phases

1. Starter template constant + `AdrProjection` port/adapter + extend UoW
2. `CreateAdrCommandHandler` + `UpdateAdrContentCommandHandler` + domain errors
3. `GetAdrQueryHandler` + `AdrRepository`
4. ADR router, schemas, bootstrap wiring
5. Integration tests (create, update, ownership isolation, reload)

### Frontend phases

1. API types + `useApi` ADR functions + Pinia store
2. Workspace "Create ADR" entry point
3. Editor page + markdown textarea component
4. `useAdrPersistence` (blur + unload)
5. Frontend tests (store + persistence composable)

### Verification

Manual: create → edit → blur → refresh → content recovered; tab close with unload save.
Automated: align with test-plan Phase 3 risk #4 when S-02 lands.
