# Command Handlers — Aggregate Source of Truth Implementation Plan

## Overview

Refactor the write path so domain aggregates are rehydrated from the append-only `events` table (not projection tables) before business decisions run. Command handlers and `RunAiReviewHandler` become thin orchestration (lock → load stream → rehydrate → call aggregate command method → build event → append → sync projection). Sync projection SQL stays imperative in the same UoW transaction. Async projection subscribers remain out of scope.

## Current State Analysis

Command handlers today load `AdrReadModel` / `UserReadModel` from projection tables, enforce rules inline, manually construct events, and update projections in the same transaction. The event store is a write log only — no `load_stream` API exists. `ADR` and `User` are anemic frozen dataclasses; `test_vocabulary_only.py` blocks lifecycle methods. F-02 intentionally deferred aggregate behavior; slices S-01–S-05 added behavior in handlers instead.

### Key Discoveries:

- `EventStore` port has `append` and `load_unprocessed` only — no per-aggregate replay (`backend/application/ports/event_store.py:20-36`)
- All five command handlers depend on `AdrRepository` or `UserRepository` for pre-write reads (`backend/infrastructure/bootstrap.py:110-117`)
- `SqlUnitOfWorkFactory` already maps `IntegrityError` on `users_email_key` and `uq_adrs_active_user_title_ci` to `EmailAlreadyTaken` / `AdrTitleAlreadyExists` (`backend/infrastructure/adapters/persistence/unit_of_work.py:58-62`)
- Partial unique index `uq_adrs_active_user_title_ci` enforces per-user case-insensitive active ADR titles (`backend/infrastructure/adapters/persistence/migrations/versions/002_adrs_active_title_unique_index.py`)
- Projection methods encode divergent review-field semantics per transition (submit clears annotations; publish preserves them) — research documents the matrix (`context/changes/command-handlers-aggregate-source-of-truth/research.md`)

## Desired End State

- Every command handler acquires a transaction-scoped PostgreSQL advisory lock on the target aggregate, loads the event stream via `EventStore.load_stream`, rehydrates via `rehydrate_adr` / `rehydrate_user`, then calls the **specific command method** for that use case with **value objects** as input (`AdrTitle`, `AdrContent`, `UserId`, …).
- **Domain events are never passed into aggregates.** Command handlers construct `ADRCreated`, `ADRSubmittedForReview`, etc. **after** the aggregate returns the new state.
- `AdrRepository` and `UserRepository` are **not** used in command handlers or `RunAiReviewHandler` (query handlers only).
- `domain/adr/rehydrate.py` (and user equivalent) is the **only** place that pattern-matches stored event types; it extracts value objects from payloads and calls aggregate **transition helpers** (VO in, `ADR` out, no invariant checks). Aggregates do not import event classes.
- Title and email uniqueness rely on existing DB constraints; violations surface as `AdrTitleAlreadyExists` / `EmailAlreadyTaken` via UoW `IntegrityError` translation (no pre-read lookups).
- `test_vocabulary_only.py` is replaced by aggregate behavior tests covering replay semantics, command-method guards, and illegal transitions.

### Verification

- `cd backend && uv run pytest` passes
- `cd backend && uv run ruff check . && uv run ty check` pass
- Manual: create ADR → edit → submit → (AI review completes) → publish; duplicate title/email return domain errors without pre-check queries

## What We're NOT Doing

- Async projections or event-driven projection subscribers (views rebuilding from a bus)
- Refactoring sync projectors to call transition helpers (imperative SQL stays; rehydrator tests cover semantics)
- Optimistic concurrency / expected-version on `append`
- `ADRSoftDeleted` command handler (event vocabulary only)
- Frontend changes

## Implementation Approach

Introduce `load_stream` on the event store, rich aggregates (VO inputs, state output — no events), rehydration modules that map stored events → VOs → transition helpers, and advisory locking on the UoW. Command handlers own event construction. Refactor handlers in dependency order: domain first (with tests), then infrastructure, then handlers.

## Critical Implementation Details

- **Advisory lock ordering:** Acquire `pg_advisory_xact_lock` at the start of the UoW body, before `load_stream` and `append`, so concurrent commands on the same aggregate serialize within the transaction.
- **Rehydration boundary:** `rehydrate_adr(events)` lives in `domain/adr/rehydrate.py`, imports event types, extracts VOs, calls aggregate transition helpers. `aggregate.py` does not import from `domain/adr/events.py`.
- **Rehydration must include async facts:** `AIReviewCompleted` and `AIReviewFailed` appear in the stream before `publish`. The rehydrator must map them to transition helpers (`record_review_completed`, `record_review_failed`, …) so `publish()` sees `after_review` state.
- **Command vs transition split:** Command methods validate invariants then delegate to transition helpers (same helpers the rehydrator uses). Transition helpers take only value objects and timestamps; they return the next `ADR` / `User`.
- **Handler builds events:** After `new_adr = adr.publish(updated_at)`, the handler constructs `ADRPublished(adr_id=new_adr.adr_id, occurred_at=updated_at)` from aggregate fields — not returned by the aggregate.
- **Ownership guard:** After rehydration, compare `aggregate.user_id` to `command.user_id`. Mismatch or empty stream → `AdrNotFound` (same security posture as today).
- **Create / register paths:** No prior stream. `create_adr` locks the new `adr_id`, appends `ADRCreated`; `register_user` locks new `user_id`, appends `UserRegistered`. Uniqueness races on title/email are caught at projection `insert` commit via existing UoW mapping.

## Phase 1: Domain & EventStore Foundation

### Overview

Add event-stream replay and rich domain aggregates with tested replay and command methods. Remove the F-02 vocabulary guardrail test.

### Changes Required:

#### 1. EventStore port — `load_stream`

**File**: `backend/application/ports/event_store.py`

**Intent**: Expose per-aggregate event replay so command handlers can rehydrate state without reading projection tables.

**Contract**: Add `async def load_stream(self, aggregate_id: UUID, aggregate_type: str) -> list[StoredEvent]` returning events ordered by `occurred_at`, then `id`.

#### 2. SqlEventStore — `load_stream` implementation

**File**: `backend/infrastructure/adapters/persistence/event_store.py`

**Intent**: Query `events` filtered by `aggregate_id` and `aggregate_type`, deserialize via existing `_EVENT_TYPES` / `_to_stored_event`.

**Contract**: `SELECT … WHERE aggregate_id = ? AND aggregate_type = ? ORDER BY occurred_at ASC, id ASC`. Reuse `_to_stored_event`; no filter on `processed_at` or event type.

#### 3. ADR aggregate — command methods and transition helpers

**File**: `backend/domain/adr/aggregate.py`

**Intent**: Make `ADR` the semantic source of truth for command-path decisions. Accept **value objects only**; never accept or return domain events. Centralize review-field and status rules scattered across handlers and projection SQL.

**Contract**:

**Command methods** (called by command handlers — handler knows which to invoke; VO inputs, `ADR` output):

- `classmethod create(adr_id: AdrId, user_id: UserId, title: AdrTitle, content: AdrContent, created_at: datetime) -> ADR` — initial `draft` state (`create_adr`; no prior stream).
- `update_content(content: AdrContent, updated_at: datetime) -> ADR` and `update_title(title: AdrTitle, updated_at: datetime) -> ADR` — each rejects `in_review`. Split mirrors `ADRContentUpdated` payload (content required, title optional).
- `submit_for_review(updated_at: datetime) -> ADR` — rejects non-`draft`; uses current `content` as review snapshot in state.
- `publish(updated_at: datetime) -> ADR` — rejects non-`after_review`.

**Transition helpers** (VO inputs, `ADR` output, **no invariant checks** — called by command methods after validation and by `rehydrate_adr` only):

- `bootstrap(...)` or reuse `create` for first `ADRCreated` fact
- `with_content_updated(content, updated_at)` and `with_title_updated(title, updated_at)` — rehydrator calls both when `ADRContentUpdated.title` is set
- `with_submitted_for_review(updated_at)` — clears review fields, `status=in_review`
- `with_review_completed(result: ReviewResult, reviewed_at: datetime)`
- `with_review_failed(code: str, message: str)` — or a small review-error VO if one exists
- `with_published(updated_at)`
- `with_soft_deleted()`

Command methods delegate to the matching transition helper after guards pass.

**State semantics** (transition helpers must match research matrix):

| Fact (from stored event) | `status` | `review_result` | `review_error` | `reviewed_at` |
|--------------------------|----------|-----------------|----------------|---------------|
| Created | `draft` | cleared | cleared | cleared |
| Content updated | unchanged | unchanged | unchanged | unchanged |
| Submitted for review | `in_review` | cleared | cleared | cleared |
| AI review completed | `after_review` | set | cleared | set |
| AI review failed | unchanged | unchanged | set | unchanged |
| Published | `proposed` | unchanged | unchanged | unchanged |
| Soft deleted | unchanged | unchanged | unchanged | `is_deleted=True` |

Illegal **command** transitions raise existing domain errors (`DomainError`, `AdrInvalidPublishStatus`, etc.) with messages compatible with current API behavior.

#### 3b. ADR rehydration — event stream → value objects → transitions

**File**: `backend/domain/adr/rehydrate.py` (new)

**Intent**: Rebuild `ADR` from a list of domain events without passing event objects into `aggregate.py`. This module is the event-type dispatch boundary.

**Contract**:

- `rehydrate_adr(events: list[DomainEvent]) -> ADR | None` — empty list → `None`; otherwise fold in order.
- For each event: extract fields / value objects from the Pydantic payload, call the matching transition helper on the current `ADR`.
- Unknown event type → raise. This module **may** import `domain.adr.events`; `aggregate.py` **must not**.

#### 4. User aggregate and rehydration

**Files**: `backend/domain/user/aggregate.py`, `backend/domain/user/rehydrate.py` (new)

**Intent**: Mirror ADR pattern for `register_user`.

**Contract**:

- `User.create(user_id, email, password_hash, created_at) -> User` — command factory (VO inputs only).
- `rehydrate_user(events) -> User | None` — maps `UserRegistered` payload to VOs → `User.create(...)`.

#### 5. Domain exports

**File**: `backend/domain/adr/__init__.py`, `backend/domain/user/__init__.py`

**Intent**: Re-export new public aggregate API if the package `__init__` files gate imports.

**Contract**: Exports remain stable for existing event/value-object imports; add aggregate methods as needed.

#### 6. Replace vocabulary guardrail test

**Files**: `backend/tests/domain/test_vocabulary_only.py` (delete), `backend/tests/domain/test_adr_aggregate.py` (new), `backend/tests/domain/test_adr_rehydrate.py` (new), `backend/tests/domain/test_user_aggregate.py` (new or extend `test_user.py`)

**Intent**: Replace the F-02 “no behavior on aggregates” test with tests for transition helpers, command-method guards, rehydrator mapping, and annotation semantics.

**Contract**: Cover at minimum: `rehydrate_adr([])` → `None`; full lifecycle via rehydrator draft → in_review → after_review → proposed; `submit_for_review` clears review fields; `publish` preserves review fields after `with_review_completed`; `update_content` during `after_review` does not clear annotations; illegal `publish()` from `draft` raises `AdrInvalidPublishStatus`. Test transition helpers, command guards, and rehydrator separately.

#### 7. EventStore unit tests

**File**: `backend/tests/infrastructure/adapters/persistence/test_event_store.py` (new or extend existing)

**Intent**: Verify `load_stream` ordering, empty stream, and deserialization for all registered event types.

**Contract**: Integration test against Postgres fixture; append multiple events for one `aggregate_id`, assert `load_stream` returns full ordered list.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_adr_rehydrate.py tests/domain/test_user_aggregate.py`
- `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_event_store.py` (or equivalent path)
- `cd backend && uv run ruff check backend/domain/ backend/application/ports/event_store.py`
- `cd backend && uv run ty check`

#### Manual Verification:

- Review replay semantics table against research annotation matrix — no contradictions

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: UoW Locking & Command Handler Refactor

### Overview

Add per-aggregate advisory locking on the UoW and refactor all five command handlers to stream-load aggregates. Remove repository pre-reads from the command path.

### Changes Required:

#### 1. Advisory lock on UnitOfWork

**Files**: `backend/application/ports/unit_of_work.py`, `backend/infrastructure/adapters/persistence/unit_of_work.py`

**Intent**: Serialize concurrent commands targeting the same aggregate using PostgreSQL transaction-scoped advisory locks.

**Contract**: Add `async def lock_aggregate(self, aggregate_id: UUID) -> None` on `UnitOfWork`. Implementation executes `pg_advisory_xact_lock` with deterministic keys derived from the UUID (document the key derivation in a one-line comment). Lock auto-releases on commit/rollback.

#### 2. CreateAdrCommandHandler

**File**: `backend/application/commands/create_adr.py`

**Intent**: Stop pre-checking title via `AdrRepository`. Create via `ADR.create(...)` command method; rely on projection unique index + UoW error mapping for duplicate titles.

**Contract**: Remove `AdrRepository` constructor dependency. Inside UoW: `lock_aggregate(new_adr_id)` → `ADR.create(...)` with VOs → build `ADRCreated` from resulting state in handler → `append` → `mark_processed` → `adr_projection.insert`. Remove `find_by_title_for_owner` block. No stream load (new aggregate).

#### 3. UpdateAdrContentCommandHandler

**File**: `backend/application/commands/update_adr_content.py`

**Intent**: Load ADR from stream; delegate `update_content` to aggregate; remove projection-based status/title checks.

**Contract**: Remove `AdrRepository` dependency. UoW flow: `lock_aggregate` → `load_stream` → `rehydrate_adr(events)` → ownership check → `adr.update_content(AdrTitle(...), AdrContent(...), updated_at)` → handler builds `ADRContentUpdated` from new state → `append` → `mark_processed` → `adr_projection.update_content`. Title conflict via DB constraint only.

#### 4. SubmitAdrForReviewCommandHandler

**File**: `backend/application/commands/submit_adr_for_review.py`

**Intent**: Submit decision from rehydrated aggregate, not `existing.status` string on read model.

**Contract**: Remove `AdrRepository` dependency. UoW: lock → load stream → `rehydrate_adr` → `submit_for_review(updated_at)` → handler builds `ADRSubmittedForReview` (content snapshot from `new_adr.content`) → append → `mark_in_review` (no `mark_processed`).

#### 5. PublishAdrCommandHandler

**File**: `backend/application/commands/publish_adr.py`

**Intent**: Publish guard uses rehydrated state (including prior `AIReviewCompleted` in stream), not projection read.

**Contract**: Remove `AdrRepository` dependency. UoW: lock → load stream → `rehydrate_adr` → `publish(updated_at)` → handler builds `ADRPublished` → append → `mark_proposed` → `mark_processed`. Keep `mark_proposed` rowcount check as defense-in-depth.

#### 6. RegisterUserCommandHandler

**File**: `backend/application/commands/register_user.py`

**Intent**: Remove email pre-read; rely on `users.email` unique constraint and existing UoW `EmailAlreadyTaken` mapping.

**Contract**: Remove `UserRepository` constructor dependency. UoW: `lock_aggregate(new_user_id)` → `User.create(...)` with VOs → handler builds `UserRegistered` → append → `mark_processed` → `user_projection.insert`.

#### 7. Bootstrap wiring

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Update handler constructors after repository dependencies are removed from commands.

**Contract**: `CreateAdrCommandHandler(uow_factory)` (and analogous for other commands). `RunAiReviewHandler(uow_factory, adr_review_service)` — no `AdrRepository`. `AdrRepository` / `UserRepository` remain wired for **query handlers only**.

#### 8. Command handler tests

**Files**: `backend/tests/application/commands/test_create_adr.py`, `test_update_adr_content.py`, `test_submit_adr_for_review.py`, `test_publish_adr.py`, `test_register_user.py`

**Intent**: Update fakes to support `load_stream` and remove repository stubs where no longer injected. Assert handlers call stream load, not repository find.

**Contract**: Existing behavioral assertions (404, invalid status, title conflict) still pass; title/email conflict tests may need to exercise UoW/integration path instead of mocking repository pre-checks.

#### 9. UoW lock test

**File**: `backend/tests/infrastructure/adapters/persistence/test_unit_of_work.py` (extend)

**Intent**: Smoke-test `lock_aggregate` does not error; optional concurrency test if straightforward with two parallel sessions.

**Contract**: At minimum: lock acquires and commits cleanly inside `uow_factory.begin()`.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/application/commands/`
- `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_unit_of_work.py`
- `cd backend && uv run ruff check .`
- `cd backend && uv run ty check`

#### Manual Verification:

- Duplicate title on create returns `AdrTitleAlreadyExists` without repository pre-read (verify via logs or temporary breakpoint — no `find_by_title` call)
- Duplicate email on register returns `EmailAlreadyTaken` similarly

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: RunAiReviewHandler & Integration Verification

### Overview

Extend the aggregate source-of-truth pattern to `RunAiReviewHandler`, then verify the full ADR lifecycle end-to-end. The async handler stops reading `AdrRepository`; it rehydrates from `load_stream` + `rehydrate_adr`, calls new aggregate command methods for review completion/failure, and builds `AIReviewCompleted` / `AIReviewFailed` in the handler after the aggregate transitions. LLM calls stay outside the write transaction; pre-flight stream load preserves skip/idempotency before invoking the LLM.

### Changes Required:

#### 1. ADR aggregate — AI review command methods

**File**: `backend/domain/adr/aggregate.py`

**Intent**: Encapsulate review outcome invariants currently enforced via projection reads in `RunAiReviewHandler`.

**Contract**:

- `complete_review(result: ReviewResult, reviewed_at: datetime) -> ADR` — requires `in_review`; delegates to `with_review_completed`.
- `fail_review(code: str, message: str) -> ADR` — requires `in_review`; delegates to `with_review_failed`.
- Add domain tests in `backend/tests/domain/test_adr_aggregate.py` for guards (e.g. reject `complete_review` when `after_review` or `draft`).

#### 2. RunAiReviewHandler refactor

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Align async write path with command handlers: event stream is operational source of truth; handler builds outcome events from aggregate state.

**Contract**:

- Remove `AdrRepository` constructor dependency.
- **Pre-flight** (before LLM, read-only — use `uow_factory.begin()` without holding advisory lock during LLM):
  - `load_stream(adr_id, "adr")` → `rehydrate_adr`
  - Skip + `mark_processed` when: stream empty / ownership mismatch (`event.user_id` vs rehydrated `adr.user_id`); `adr.status == after_review`; stream already contains `AIReviewFailed` with `source_event_id == stored_event.id`
  - Use `event.content` from trigger `ADRSubmittedForReview` for LLM markdown (dispatch payload — not passed into aggregate)
- **Persist** (after LLM success or terminal failure):
  - `lock_aggregate(adr_id)` → `load_stream` → `rehydrate_adr` → re-check idempotency guards
  - Success: `new_adr = adr.complete_review(result, reviewed_at)` → handler builds `AIReviewCompleted` → `append` → `apply_review_result` → `mark_processed` (outcome + source submit event)
  - Failure: `new_adr = adr.fail_review(code, message)` → handler builds `AIReviewFailed` (include `source_event_id=stored_event.id`) → `append` → `record_review_failure` → `mark_processed` (outcome + source)
- Preserve existing logging keys and retry loop (`_MAX_ATTEMPTS`, validation feedback).

#### 3. Bootstrap wiring

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Drop `adr_repository` from `RunAiReviewHandler` construction.

**Contract**: `RunAiReviewHandler(uow_factory, adr_review_service)` only.

#### 4. RunAiReviewHandler tests

**File**: `backend/tests/application/handlers/test_run_ai_review.py`

**Intent**: Replace `FakeAdrRepository` with stream-based fakes; assert `load_stream` + rehydration drive skip and persist paths.

**Contract**:

- Extend `FakeEventStore` with `load_stream` returning a configurable ordered `list[StoredEvent]` per `aggregate_id`.
- Build streams via helpers (e.g. `ADRCreated` + `ADRSubmittedForReview` for happy path; add `AIReviewCompleted` for idempotent skip; add `AIReviewFailed` with matching `source_event_id` for duplicate-failure skip).
- Remove `FakeAdrRepository` usage; update all five existing tests plus ownership-mismatch skip if not covered.
- Assert `lock_aggregate` called on persist UoW; assert handler builds `AIReviewCompleted` / `AIReviewFailed` with expected payloads.

#### 5. Event-store integration test — full lifecycle replay

**File**: `backend/tests/infrastructure/adapters/persistence/test_event_store.py` or new `test_command_path_aggregate_load.py`

**Intent**: Prove a realistic stream (create → update → submit → `AIReviewCompleted` → publish) rehydrates to the state `publish()` expects.

**Contract**: Append events in order for one `aggregate_id`; `rehydrate_adr([e.event for e in await load_stream(...)])` has `status=AFTER_REVIEW` before publish event; after including `ADRPublished`, `status=PROPOSED`.

#### 6. API integration smoke (existing test suite)

**Files**: existing router integration tests under `backend/tests/infrastructure/api/` if present

**Intent**: Ensure HTTP layer still maps domain errors correctly.

**Contract**: No router changes expected; run existing ADR/user API tests.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/domain/test_adr_aggregate.py` (review command methods)
- `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py`
- `cd backend && uv run pytest`
- `pre-commit run --all-files` (from repo root)

#### Manual Verification:

- `just dev-backend` + exercise create → edit → submit → wait for AI review → publish via API or curl
- Confirm `RunAiReviewHandler` completes using stream-loaded state (no projection read in handler)
- Confirm query endpoints (`GET /api/adrs/{id}`) return expected projection state after review completes

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful.

---

## Testing Strategy

### Unit Tests:

- `ADR` transition helpers and command methods — guards, illegal transitions, annotation semantics
- `rehydrate_adr` — all event types mapped to VO → transition calls
- `RunAiReviewHandler` — stream-load, `complete_review` / `fail_review`, handler-built outcome events
- Command handlers — assert events built with correct payloads after aggregate transition
- `User.register` / `from_events`
- Command handlers with fake `EventStore` returning predetermined streams

### Integration Tests:

- `load_stream` ordering and deserialization
- UoW `IntegrityError` → domain error (existing + post-refactor create/update title races)
- Full-stream rehydration including `AIReviewCompleted` before publish
- `RunAiReviewHandler` idempotency via stream contents (`after_review`, duplicate `AIReviewFailed`)

### Manual Testing Steps:

1. Register two users; second with duplicate email → `409` / `EmailAlreadyTaken`
2. Create ADR; create second with same title (case-insensitive) → `AdrTitleAlreadyExists`
3. Edit ADR in `draft`; attempt edit in `in_review` after submit → rejected
4. Submit → AI review → publish; confirm annotations preserved on publish per product rules
5. Attempt publish from `draft` → `AdrInvalidPublishStatus`

## Performance Considerations

- `load_stream` reads all events for an aggregate on every command — acceptable for MVP ADR lifecycles (typically &lt;20 events). No snapshot table in this change.
- Advisory locks serialize per-aggregate writes only; different ADRs remain parallel.

## Migration Notes

No schema migration required. Existing events rehydrate correctly if transition helpers match historical projection semantics.

## References

- Research: `context/changes/command-handlers-aggregate-source-of-truth/research.md`
- Architecture: `context/foundation/application-architecture.md`
- Publish handler (projection-first baseline): `backend/application/commands/publish_adr.py`
- UoW constraint mapping: `backend/infrastructure/adapters/persistence/unit_of_work.py:58-76`
- Title unique index: `backend/infrastructure/adapters/persistence/migrations/versions/002_adrs_active_title_unique_index.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Domain & EventStore Foundation

#### Automated

- [x] 1.1 `cd backend && uv run pytest tests/domain/test_adr_aggregate.py tests/domain/test_user_aggregate.py` — 38430f3
- [x] 1.2 `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_event_store.py` (or equivalent path) — 38430f3
- [x] 1.3 `cd backend && uv run ruff check backend/domain/ backend/application/ports/event_store.py` — 38430f3
- [x] 1.4 `cd backend && uv run ty check` — 38430f3

#### Manual

- [x] 1.5 Review replay semantics table against research annotation matrix — no contradictions — 38430f3

### Phase 2: UoW Locking & Command Handler Refactor

#### Automated

- [x] 2.1 `cd backend && uv run pytest tests/application/commands/` — d0b06a8
- [x] 2.2 `cd backend && uv run pytest tests/infrastructure/adapters/persistence/test_unit_of_work.py` — d0b06a8
- [x] 2.3 `cd backend && uv run ruff check .` — d0b06a8
- [x] 2.4 `cd backend && uv run ty check` — d0b06a8

#### Manual

- [ ] 2.5 Duplicate title on create returns `AdrTitleAlreadyExists` without repository pre-read
- [ ] 2.6 Duplicate email on register returns `EmailAlreadyTaken` without repository pre-read

### Phase 3: RunAiReviewHandler & Integration Verification

#### Automated

- [x] 3.1 `cd backend && uv run pytest tests/domain/test_adr_aggregate.py` (review command methods) — 9dc1a42
- [x] 3.2 `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py` — 9dc1a42
- [x] 3.3 `cd backend && uv run pytest` — 9dc1a42
- [x] 3.4 `pre-commit run --all-files` (from repo root) — 9dc1a42

#### Manual

- [ ] 3.5 Exercise create → edit → submit → AI review → publish via API
- [ ] 3.6 Confirm `RunAiReviewHandler` uses stream-loaded state (no `AdrRepository` read)
- [ ] 3.7 Confirm query endpoints return expected projection state after review completes
