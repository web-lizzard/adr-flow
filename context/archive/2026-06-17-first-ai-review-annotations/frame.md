# Frame Brief: Client Polling in S-04

> Framing step before /plan. This document captures what is *actually*
> at issue, separated from what was initially assumed.

## Reported Observation

User asked how to understand **"client pooling"** in the context of
`first-ai-review-annotations` plan — specifically what mechanism the
frontend should use while an ADR is `in_review` waiting for AI review to
complete.

## Initial Framing (preserved)

- **User's stated cause or approach**: Assumed "client pooling" is a named
  pattern from the plan that must be understood before implementation.
- **User's proposed direction**: Clarify the concept so S-04 frontend/backend
  work can proceed with the right mental model.
- **Pre-dispatch narrowing**: User confirmed the concern is **client
  polling** (periodic status checks), not connection pooling (HTTP/DB
  connection reuse).

## Dimension Map

The observation could originate at any of these dimensions:

1. **Terminology mismatch** — plan/research say "polling", not "pooling";
   user may have misread or conflated with SQLAlchemy/httpx connection pools
2. **Notification mechanism choice** — polling vs SSE vs webhooks for
   telling the browser review finished ← user's implicit question lands here
3. **Polling contract split** — lightweight `review-status` poll vs full ADR
   refetch on completion
4. **Separation from backend worker** — polling observes async worker output;
   it does not trigger `RunAiReview`

## Hypothesis Investigation

| Hypothesis | Evidence | Verdict |
| --- | --- | --- |
| Terminology: plan uses "polling" not "pooling" | `research.md` L123, `plan-brief.md` L26, `plan.md` L5/L17/L321; grep finds zero "pooling" in change docs; only DB `pool_pre_ping` in `bootstrap.py` | STRONG |
| Mechanism choice: client polling for MVP | `research.md` L115–157 follow-up compares poll/SSE/webhook; decision L155–157; `plan-brief.md` L26–27, L52; `plan.md` L35 excludes SSE/webhooks | STRONG |
| Contract split: status endpoint then full refetch | `plan.md` L17, L194–196, L321–327; `research.md` L147–151; `useApi.ts` L51–53 today only has full `fetchAdr` | STRONG |
| Polling ≠ worker trigger | `application-architecture.md` L120–122; `plan.md` L188 (dispatch on submit), L192–196 (status is read-only query); `plan-brief.md` L18, L58 | STRONG |
| Connection pooling is the S-04 frontend concern | `bootstrap.py` L40 `pool_pre_ping` is Postgres only; OpenRouter adapter may use httpx but no client-pool design in plan | NONE |

## Narrowing Signals

- User explicitly chose "client polling" over "connection pooling" when
  disambiguated — rules out httpx/SQLAlchemy pool as the primary question.
- Step 3 found strong evidence on all four polling dimensions and none for
  connection pooling as S-04 scope.
- No existing frontend polling in codebase; S-04 introduces the first
  interval-based completion-discovery pattern (`plan-brief.md` L14).

## Cross-System Convention

This project today uses **mount-time `$fetch` + Pinia store loads** only
(`[id].vue` L19–21, `adr.ts` L106–114). No `useInterval`, SSE, or
WebSocket patterns exist. Foundation stack sets `has_realtime: false`
(`tech-stack.md` L41). S-04 research explicitly chose polling as the first
completion-discovery mechanism, deferring SSE to a possible phase-2.

## Reframed (or Confirmed) Problem Statement

> **The actual problem to plan around is**: understand **client polling** as
> the frontend's read-only way to discover when the backend async review
> worker has finished — not as "pooling", not as the worker itself, and not
> as polling the full ADR body on every tick.

In S-04, two independent loops run in parallel after submit:

1. **Backend (event-driven)**: `POST submit-review` → `ADRSubmittedForReview`
   persisted → dispatcher schedules `RunAiReview` → LLM + validation →
   projection updates to `after_review` (or records `review_error` while
   staying `in_review`).
2. **Frontend (poll-driven observation)**: while status is `in_review`, the
   editor periodically calls `GET review-status` (lightweight: status,
   timestamps, error metadata, optional annotation counts). When status leaves
   `in_review` or terminal error appears, polling stops and the page calls
   `adr.load(id)` once to fetch full annotations.

Polling was chosen over SSE/webhooks because the MVP has no realtime channel,
Cloud Run scale-to-zero favors short HTTP requests, and cookie-session auth
fits simple same-origin GETs (`research.md` L126–136).

## Confidence

**HIGH** — terminology clarified by user; mechanism decision is documented
in research and plan; separation from backend worker is explicit in
architecture; no contradictory evidence in codebase.

## What Changes for /plan

No plan restructure needed. The existing plan already describes client
polling correctly. Implementation should treat polling as a **new frontend
pattern** (`useAdrReviewPolling.ts`) on top of existing `load()` refetch,
with a dedicated lightweight backend query — not extend full-ADR fetches on
an interval, and not confuse polling requests with worker dispatch.

## References

- `context/changes/first-ai-review-annotations/research.md` L115–157
- `context/changes/first-ai-review-annotations/plan-brief.md` L18, L26–27, L40, L58
- `context/changes/first-ai-review-annotations/plan.md` L17, L35, L188–196, L321–327
- `context/foundation/application-architecture.md` L112–124, L157–166
- `context/foundation/tech-stack.md` L41, L48
- `frontend/app/pages/workspace/adr/[id].vue` L15, L19–21
- `frontend/composables/useApi.ts` L51–53
- `frontend/app/stores/adr.ts` L106–114
- Investigation tasks: notification choice, polling contract, worker separation, cross-system patterns (2026-06-17)
