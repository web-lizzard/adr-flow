---
project: adr-flow
version: 1
status: draft
created: 2026-06-13
updated: 2026-06-14
related:
  - infrastructure.md
  - tech-stack.md
  - roadmap.md
style: hexagonal
patterns:
  - event-sourcing-lite
  - cqrs-lite
---

# Application Architecture

> Backend application structure for adr-flow. Deployment, event dispatch transport, and platform choices live in [infrastructure.md](infrastructure.md). This document defines how the FastAPI backend is organised and how writes and reads flow through it.

## Summary

The backend uses **hexagonal architecture** (ports and adapters) with **CQRS lite** and **event sourcing lite**:

- **Writes** go through command handlers → domain aggregates → append-only `events` table → projection updates.
- **Reads** go through query handlers → projection tables (`users`, `adrs`) — no aggregate load, no stream replay.
- **Side effects** (e.g. AI review) run in **event handlers** dispatched asynchronously after an event is persisted.

`domain/` holds pure business logic. `application/` orchestrates use cases and defines ports. `infrastructure/` implements adapters (HTTP, SQL, LLM) and wires everything in bootstrap.

## Layers

| Layer | Responsibility | Depends on |
|---|---|---|
| `domain/` | Aggregates, value objects, domain events, invariants, state transitions | nothing external |
| `application/` | Command handlers, query handlers, ports (interfaces), runtime dispatcher
| `infrastructure/` | FastAPI routers, Pydantic schemas, SQL adapters, LLM client, event-bus implementation, migrations, bootstrap | `application/`, `domain/` |

**Hexagonal rule:** `domain/` and `application/` never import FastAPI, SQL drivers, or HTTP clients. Adapters in `infrastructure/` implement ports defined in `application/`.

## CQRS lite

CQRS lite separates **command** and **query** code paths without separate databases or eventual-consistency complexity.

### Commands (write side)

A command represents an intent to change state (e.g. `RegisterUser`, `SubmitAdrForReview`).

1. Driving adapter (HTTP router) parses the request and builds a command.
2. Command handler loads or creates the aggregate.
3. Aggregate applies business rules and emits domain event(s).
4. Events are appended to the `events` table (source of truth).
5. Projector updates read-model tables (`users`, `adrs`).
6. Runtime dispatcher schedules event handlers for the new event(s).

Commands never return domain aggregates to the API layer; they return a simple result (ID, status, or void).

### Queries (read side)

A query represents a read intent (e.g. `GetAdr`, `ListAdrs`).

1. Driving adapter parses the request and builds a query.
2. Query handler reads directly from projection tables.
3. Result is mapped to a response schema.

Queries do not load aggregates, emit events, or touch the event store.

### What "lite" excludes (MVP)

- Separate read database or materialised-view pipeline
- Generic command-bus framework with middleware pipelines
- Stream replay on every GET request
- Full strategic DDD (bounded-context maps, context integration patterns)

## Event sourcing lite

Postgres stores an append-only **`events`** table as the write-side source of truth. Projection tables (`users`, `adrs`) are derived views optimised for queries.

### `events` table (required)

Every state change is recorded as an immutable row. Minimum contract:

| Column | Purpose |
|---|---|
| `id` | Surrogate key (ordering) |
| `aggregate_type` | e.g. `adr`, `user` |
| `aggregate_id` | UUID of the aggregate instance |
| `event_type` | e.g. `ADRSubmittedForReview` |
| `payload` | JSON event data |
| `occurred_at` | When the event happened |
| `processed_at` | `NULL` until all handlers complete; used for startup replay |

New events are always **appended**; existing rows are never updated or deleted.

### Projection tables (read models)

| Table | Role |
|---|---|
| `users` | Current user state (email, password hash, timestamps) |
| `adrs` | Current ADR state (title, markdown content, status, `user_id`, soft-delete flag, timestamps) |

Projections are updated synchronously in the command handler path (same transaction as the event append when possible). They exist so queries stay fast and simple.

### Ownership scope

ADR aggregates reference their owner **by identity** — a single UUID on the aggregate and on the `adrs` projection (`user_id`). They do not embed `User` state.

In MVP, **treat `user_id` as the ownership scope**; today scope equals the authenticated user (per-user isolation). Post-MVP workspaces can introduce `workspace_id` as scope while `user_id` records the author — an additive migration (add column, backfill personal workspaces), not a rewrite of the ADR model, because ownership is already a reference-by-identity.

**Enforce isolation in one place:** command handlers and query handlers validate scope before load or read (e.g. list and fetch ADRs filtered by the caller's scope). Do not scatter ownership checks across routers or projection adapters. That seam is the single point to extend when scope becomes workspace membership instead of user id.

### Startup replay

On application start, unprocessed events (`processed_at IS NULL`) are loaded and their handlers re-run. This replaces any in-memory queue lost during scale-to-zero or restart. Handlers must be **idempotent**. See [infrastructure.md](infrastructure.md) for dispatch transport details.

## Domain events and async handlers

Domain events are facts that already happened (past tense): `UserRegistered`, `ADRCreated`, `ADRSubmittedForReview`, `AIReviewCompleted`, `ADRPublished`, `ADRSoftDeleted`.

**Command dispatch** is synchronous within the HTTP request (steps 1–5 above).

**Event dispatch** is asynchronous: after an event is persisted, the runtime dispatcher invokes registered handlers via `asyncio.TaskGroup` (MVP). Example: `ADRSubmittedForReview` → `RunAiReview` handler → calls LLM adapter → appends `AIReviewCompleted` → updates projection.

The worker lives in `application/runtime/`; the TaskGroup implementation lives in `infrastructure/messaging/`.

## Module layout

```
backend/
  domain/
    user/           # User aggregate, events, invariants
    adr/            # ADR aggregate, events, status transitions
  application/
    commands/       # One handler per write use case
    queries/        # One handler per read use case
    handlers/       # Async event handlers (side effects)
    ports/          # Protocols: EventStore, EventBus, LlmCompletionPort, …
    services/       # AdrReviewService (review orchestration)
    runtime/        # Handler registry + dispatch loop
  infrastructure/
    api/
      routers/      # FastAPI route modules (driving adapters)
      schemas/      # Pydantic request/response models
    adapters/
      persistence/
        event_store.py
        projections/  # users, adrs read/write adapters
    llm/            # OpenAI SDK completion client + fake port
    messaging/      # asyncio TaskGroup event-bus implementation
    bootstrap.py    # Composition root: wire ports → adapters
  main.py           # Thin FastAPI app + lifespan (startup replay)
```

Organise by **feature inside each layer** (`domain/adr/`, `commands/create_adr.py`), not by technical type at the top level.

## Request flows

### Write example: submit ADR for review

```
HTTP POST  →  infrastructure/api/routers/adr.py
           →  application/commands/submit_adr_for_review.py
           →  domain/adr/aggregate.py  (emits ADRSubmittedForReview)
           →  infrastructure/adapters/persistence/event_store.py  (append)
           →  infrastructure/adapters/persistence/projections/adrs.py  (status → in_review)
           →  application/runtime/dispatcher.py  (schedule handler)
           →  application/handlers/run_ai_review.py  (async, after response)
```

### Read example: list ADRs

```
HTTP GET   →  infrastructure/api/routers/adr.py
           →  application/queries/list_adrs.py
           →  infrastructure/adapters/persistence/projections/adrs.py  (SELECT)
           →  response schema
```

## Vertical slices

Each roadmap slice (S-01, S-02, S-04, …) adds a narrow vertical strip:

| Slice | Typical additions |
|---|---|
| S-01 Account access | `domain/user/`, `commands/register_user.py`, `queries/get_current_user.py`, auth router |
| S-02 Draft authoring | `domain/adr/`, `commands/create_adr.py`, `commands/update_adr_content.py`, ADR router |
| S-04 AI review | `handlers/run_ai_review.py`, `services/adr_review_service.py`, `infrastructure/llm/openai_sdk_client.py` |
| S-05 Publish | `commands/publish_adr.py` (emits `ADRPublished`) |
| S-06 Soft delete | `commands/soft_delete_adr.py` (emits `ADRSoftDeleted`) |

Foundation slice F-02 (`persistence-scaffold`) delivers the `events` table, projection tables, port definitions, bootstrap skeleton, and empty dispatcher — not feature routers or business logic.

## References

- [infrastructure.md](infrastructure.md) — platform, Postgres event store, asyncio dispatch, replay risks
- [tech-stack.md](tech-stack.md) — FastAPI backend, split-stack boundaries
- [roadmap.md](roadmap.md) — slice ordering and F-02 scope
