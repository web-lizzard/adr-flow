---
date: 2026-06-17T01:48:00+02:00
researcher: Codex 5.3
git_commit: 0964f85575eb845d74a0fa475750877084a33ffd
branch: main
repository: adr-flow
topic: "S-04 first-ai-review-annotations: async worker requirements and LLM adapter boundary"
tags: [research, codebase, first-ai-review-annotations, backend, async-worker, llm-adapter]
status: complete
last_updated: 2026-06-17
last_updated_by: Codex 5.3
last_updated_note: "Added follow-up research for Nuxt client notification when review completes"
---

# Research: S-04 first-ai-review-annotations (async worker + LLM adapter)

**Date**: 2026-06-17T01:48:00+02:00
**Researcher**: Codex 5.3
**Git Commit**: `0964f85575eb845d74a0fa475750877084a33ffd`
**Branch**: `main`
**Repository**: `adr-flow`

## Research Question

What is required in slice `first-ai-review-annotations` to implement:
- an async worker in the Python application layer, and
- an adapter boundary for LLM calls?

## Summary

S-04 requires a one-shot review flow `draft -> in_review -> after_review`, where review runs asynchronously and emits actionable annotations in three categories: `missing_section`, `inconsistency`, and `conciseness`. The codebase already has the domain model (`ReviewResult`, review events, ADR status enum), persistence columns (`review_annotations`, `reviewed_at`), and F-01 quality harness; however, the async runtime and LLM adapter are not implemented yet.

The required implementation for this slice is:
1. a submit-for-review command/use case and route that moves ADR to `in_review`,
2. an async event dispatcher + `RunAiReview` handler in application runtime,
3. a `LlmReviewer`-style application port and OpenRouter infrastructure adapter returning `ReviewResult`,
4. projection updates to write review annotations and transition to `after_review`,
5. guardrail validation of LLM output using the F-01 grading rules before exposing results.

## Detailed Findings

### S-04 Product and Acceptance Requirements

- S-04 outcome explicitly includes actionable annotations for missing sections, inconsistencies, and conciseness in `after_review` ([roadmap](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/roadmap.md#L116-L127)).
- PRD references for S-04 are FR-007/008/010/011/012, i.e., lifecycle transitions, publish-for-review trigger, and three annotation classes ([roadmap](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/roadmap.md#L118-L121), [prd](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/prd.md#L101-L115)).
- The review runs once per ADR in MVP (no re-review after edits) ([prd](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/prd.md#L103-L103), [prd](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/prd.md#L168-L168)).
- Actionability is part of the quality contract: detected issues must have concrete corrective proposals ([prd](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/prd.md#L134-L135)).

### Async Worker Requirement (Application Layer)

- Architecture doc already specifies async event flow: `ADRSubmittedForReview -> RunAiReview handler -> LLM adapter -> AIReviewCompleted -> projection update` ([application architecture](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L116-L124)).
- Planned runtime location is `application/runtime` with TaskGroup-based dispatch in MVP, but these runtime modules are currently missing in backend source ([application architecture](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L128-L150)).
- Existing command handlers already establish the transaction pattern for writes (`uow_factory.begin()`, append event + update projection atomically), which S-04 should follow ([create_adr command](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/application/commands/create_adr.py#L35-L74), [sql uow](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/adapters/persistence/unit_of_work.py#L40-L63)).
- `events.processed_at` already exists in persistence and provides the seam for async dispatch/replay/idempotency handling ([models](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/adapters/persistence/models.py#L16-L24)).

### LLM Adapter Requirement (Ports and Infrastructure)

- The backend uses explicit `application/ports` + `infrastructure/adapters` for boundaries, but no LLM port/adapter exists yet ([ports tree pattern](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/application/ports/adr_repository.py#L19-L38), [bootstrap wiring](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/bootstrap.py#L35-L63)).
- S-04 architecture names an OpenRouter adapter target path (`infrastructure/llm/openrouter.py`) and app-layer reviewer port concept (`LlmReviewer`) ([application architecture](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L137-L139), [application architecture](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L145-L150), [application architecture](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L186-L186)).
- Deploy config already anticipates `OPENROUTER_API_KEY`, but backend runtime settings do not yet expose it; this must be added for the adapter to function locally and in prod ([deploy secrets](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/deploy/gcp/secrets.env.example#L14-L15), [settings](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/config.py#L13-L27)).

### Existing Domain Contract to Reuse

- Review payload contract already exists and should be the adapter output: `ReviewResult` with `ReviewAnnotation` kinds `missing_section|inconsistency|conciseness` ([value objects](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/domain/adr/value_objects.py#L51-L71)).
- Domain events for async flow are already defined: `ADRSubmittedForReview` and `AIReviewCompleted` ([events](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/domain/adr/events.py#L19-L25)).
- Persistence projection already stores `review_annotations` and `reviewed_at`, so S-04 mainly needs command/handler wiring and projection methods for review updates ([adr projection](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/adapters/persistence/projections/adr_projection.py#L37-L48)).

### F-01 Quality Harness as S-04 Gate

- F-01 intentionally did not implement LLM runtime; it delivered grading harness and parser contracts for S-04 integration ([f-01 plan](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/archive/2026-06-16-review-quality-checks/plan.md#L36-L43)).
- S-04 should run LLM output through existing grader rules before persisting/serving annotations, including kind-specific actionability checks ([grader](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/tests/review_quality/grader.py#L53-L95)).
- Required sections parser and fixtures are ready to evaluate missing/empty section detection quality under the fixed heading contract (`Context`, `Options`, `Decision`, `Status`, `Consequences`) ([required sections](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/domain/adr/required_sections.py#L6-L12), [tests](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/tests/domain/adr/test_required_sections.py#L88-L112)).

## Code References

- `context/foundation/roadmap.md` - S-04 scope, dependencies, PRD refs, status.
- `context/foundation/prd.md` - FR-007/008/010/011/012, one-shot review, actionability, non-goals.
- `context/foundation/application-architecture.md` - planned async runtime and LLM adapter topology.
- `backend/domain/adr/value_objects.py` - `ReviewResult`, annotation kinds.
- `backend/domain/adr/events.py` - review lifecycle domain events.
- `backend/application/commands/create_adr.py` - write-side handler/UoW pattern to mirror.
- `backend/infrastructure/adapters/persistence/unit_of_work.py` - transaction boundary implementation.
- `backend/infrastructure/adapters/persistence/models.py` - events `processed_at` and ADR review columns.
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py` - projection update seam for reviews.
- `backend/tests/review_quality/grader.py` - actionability and verdict contract.
- `context/archive/2026-06-16-review-quality-checks/plan.md` - what F-01 implemented vs deferred to S-04.

## Architecture Insights

- This codebase expects side effects to be triggered by domain events and executed asynchronously outside the HTTP request path.
- The app-layer command/handler pattern is already stable; S-04 should add one command (`submit_adr_for_review`) plus one async handler (`run_ai_review`) rather than inventing a new orchestration style.
- The LLM boundary should be a narrow application port (`markdown -> ReviewResult`), keeping provider details in infrastructure and preserving testability via fakes.
- S-04 can reuse F-01 grading to enforce output quality at runtime without coupling business logic to LLM response phrasing.

## Historical Context (from prior changes)

- `context/archive/2026-06-16-review-quality-checks/research.md` - defines F-01 as checker-only foundation and explicitly leaves async runtime + LLM integration to S-04.
- `context/archive/2026-06-16-review-quality-checks/plan.md` - excludes OpenRouter, `RunAiReview`, and submit-for-review flow from F-01 scope.
- `context/archive/2026-06-16-draft-authoring-persistence/research.md` - establishes S-02 completion as prerequisite for review submission flow.
- `context/changes/roadmap-github-issues-proposal.md` - gives explicit issue-level S-04 input/output and flow acceptance wording.

## Related Research

- `context/changes/persistence-scaffold/research.md`
- `context/archive/2026-06-16-review-quality-checks/research.md`
- `context/archive/2026-06-16-draft-authoring-persistence/research.md`
- `context/archive/2026-06-15-testing-critical-path-domain-auth/research.md`

## Open Questions

- Should failed LLM runs transition ADR to a recoverable status or remain `in_review` with retry semantics (and where is retry policy encoded)?
- Should `ReviewResult` validation live in domain constructors, application handler guard logic, or both?
- What is the minimum retry/timeout strategy for MVP to avoid stuck reviews while keeping implementation small?

## Follow-up Research 2026-06-17T01:55:29+02:00

### Research Question

How should the system notify the Nuxt client when review status changes (`in_review` to `after_review`): webhook or server-sent events?

### Recommendation

For this product slice and current architecture, use **client polling** as the primary mechanism.
Treat **SSE** as a later UX enhancement, and do **not** use webhooks for first-party browser notification.

### Why Polling Is Best for S-04

- Frontend currently uses Pinia + imperative `$fetch` with mount-time loads; there is no realtime channel in app code to extend directly ([editor page load](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/frontend/app/pages/workspace/adr/%5Bid%5D.vue#L19-L21), [store load](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/frontend/app/stores/adr.ts#L106-L114), [api wrapper](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/frontend/composables/useApi.ts#L51-L53)).
- Stack and product guidance de-emphasize realtime/persistent connections in MVP (`has_realtime: false`, "frontend calls the API", no persistent connections) ([tech stack](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/tech-stack.md#L41-L48), [infrastructure](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/infrastructure.md#L49-L49)).
- Cloud Run profile (`min=0`, `max=1`) plus planned replay/idempotency makes polling operationally simpler and more robust than keeping long-lived streams during early MVP ([run flags](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/deploy/gcp/run-api.flags#L12-L23), [application architecture replay note](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/application-architecture.md#L112-L115)).
- PRD explicitly accepts no progress indicator/SLA in MVP; polling still satisfies completion discovery without introducing extra product surface now ([prd non-goal](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/context/foundation/prd.md#L179-L185)).

### Why Not Webhooks for This

- Webhooks are server-to-server callbacks and do not map well to your own browser client/session flow.
- Current auth model is cookie session over same-origin `/api`; polling fits naturally without extra callback signing/delivery infrastructure ([auth cookie flow](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/backend/infrastructure/api/dependencies.py#L18-L75), [nuxt proxy](https://github.com/web-lizzard/adr-flow/blob/0964f85575eb845d74a0fa475750877084a33ffd/frontend/server/routes/api/%5B...path%5D.ts#L7-L13)).

### SSE as Phase-2 (Optional)

SSE can be added later for improved responsiveness once S-04 core flow is stable:
- event stream endpoint under `/api`,
- reconnect with cursor/`Last-Event-ID`,
- idempotent replay from persisted events.

This is a valid evolution, but heavier than needed for first delivery of S-04.

### Suggested Minimal Contract

- `POST /api/adrs/{adr_id}/submit-review` -> set `in_review`, return fast (`202`).
- `GET /api/adrs/{adr_id}/review-status` -> return status + timestamps (+ optional annotation counts).
- Nuxt editor page: poll while status is `in_review` (e.g., 2-5s interval with backoff), stop when status changes, then fetch full ADR including annotations.

### Decision

**Implement polling now.**
**Do not implement webhook for browser notification.**
**Revisit SSE only if pilot UX data shows polling latency/refresh behavior is insufficient.**

