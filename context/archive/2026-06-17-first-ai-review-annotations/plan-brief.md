# First AI Review Annotations — Plan Brief

> Full plan: `context/changes/first-ai-review-annotations/plan.md`
> Research: `context/changes/first-ai-review-annotations/research.md`

## What & Why

Build S-04: the first real AI review loop. A user submits a draft ADR, the backend runs an async LLM review, and the editor shows actionable missing-section, inconsistency, and conciseness annotations when the ADR reaches `after_review`.

This is the product wedge from the PRD: ADR Flow is not just a markdown editor; it helps a tech lead turn a first draft into a shorter, more complete ADR before human review.

## Starting Point

The backend already has the review domain vocabulary and storage columns, but not the command/API/worker/LLM runtime that produces review annotations. The frontend already has an ADR editor and store, but no submit action, no polling, and no annotation UI.

## Desired End State

The user clicks "Publish for review" on a draft, sees the editor lock in `in_review`, and waits while the page polls a lightweight review-status endpoint. When the worker completes, the page refetches the ADR, status becomes `after_review`, the editor becomes editable again, and a normal annotation panel displays actionable review findings.

Failure is recoverable: provider or validation failure keeps the ADR in `in_review` with error metadata instead of silently losing the review request.

## Key Decisions Made

| Decision | Choice | Why | Source |
| --- | --- | --- | --- |
| Completion notification | Client polling | Fits current Nuxt `$fetch`/Pinia architecture and avoids SSE/webhooks for MVP. | Research |
| Worker delivery | At-least-once with idempotent handler | Uses persisted `events.processed_at` and survives restart/scale-to-zero without pretending exactly-once is available. | Plan |
| Failed review state | Stay `in_review` with retry/error metadata | Keeps the review recoverable without inventing a new lifecycle status. | Plan |
| Invalid LLM output | Retry once, then record terminal failure | Protects users from bad annotations while avoiding infinite replay loops. | Plan |
| Provider setup | Settings-driven local OpenAI-compatible, OpenRouter, and fake reviewers | Supports local API development, production OpenRouter, and deterministic tests. | Plan |
| HTTP client | Provider adapters use `httpx.AsyncClient` | LLM calls run inside async worker code without blocking the event loop. | Plan |
| Dispatch timing | TaskGroup bus runs after request lifecycle | Submit returns `202` quickly and review work continues outside the FastAPI request handler. | Plan |
| Annotation UI | Separate annotation panel | Delivers useful feedback now without the complexity of CodeMirror inline overlays. | Plan |
| Submitted content | Event carries content snapshot | Ensures review evaluates the ADR exactly as submitted. | Plan |
| Scope boundary | Exclude publish, inline overlays, SSE/webhooks | Keeps S-04 focused; S-05 owns publishing to `proposed`. | Research / Plan |

## Scope

**In scope:**

- Submit-for-review command and `POST /api/adrs/{id}/submit-review`.
- `GET /api/adrs/{id}/review-status` for polling.
- Async event dispatcher/replay and `RunAiReview` handler.
- `LlmReviewer` port, fake reviewer, local OpenAI-compatible adapter, and OpenRouter adapter.
- Production-safe review validation derived from F-01 rules.
- Persisted review annotations, reviewed timestamp, and review error metadata.
- Nuxt submit CTA, polling, read-only wait state, and annotation panel.

**Out of scope:**

- Publishing reviewed ADRs to `proposed`.
- Re-review after edits.
- Inline editor annotation overlays.
- SSE, webhooks, email notification, or progress percentage.
- Configurable ADR section conventions.
- Full semantic inconsistency scoring.

## Architecture / Approach

The backend remains hexagonal/CQRS-lite: route -> command -> event append + projection update -> post-response async dispatcher -> LLM reviewer port -> completion/failure event -> projection update. Provider calls go through async `httpx.AsyncClient` adapters. The frontend stays simple: submit through the store, poll review status while `in_review`, then refetch the full ADR when review completes.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend contracts and validation | Review metadata, event-store replay methods, API schemas, production validator, provider settings | Accidentally depending on test-only grader code |
| 2. Submit API, worker, LLM adapter | Backend submit route, post-response async handler, fake/local/OpenRouter reviewers, retry/failure behavior | Review work accidentally running inside the request lifecycle |
| 3. Frontend submit/poll/panel | User-facing submit CTA, polling, editable `after_review`, annotation panel | UX confusion during `in_review` wait or failure |
| 4. End-to-end verification | Success/failure/replay/ownership tests and fixture quality gate | Missing a cross-layer edge case |

**Prerequisites:** S-02 draft authoring and F-01 review-quality checks are already complete.
**Estimated effort:** ~3-4 focused sessions across 4 phases.

## Open Risks & Assumptions

- OpenRouter or local OpenAI-compatible structured output may need prompt iteration before it reliably passes validation.
- The MVP accepts a simple `in_review` wait state; pilot feedback may later require SSE/email/progress UX.
- `AIReviewFailed` and `review_error` are new contracts; implementation should keep them small and additive.
- Automated tests should use the fake reviewer or mocked async HTTP transports; live provider checks are manual or environment-gated.

## Success Criteria (Summary)

- A draft can be submitted, reviewed asynchronously, and returned as `after_review` with actionable annotations.
- Bad provider output does not reach the user; it records recoverable review error metadata.
- Frontend shows a simple review wait state, then displays annotations and allows editing in `after_review` without re-review.
