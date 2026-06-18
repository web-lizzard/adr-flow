# LLM Layer Refactor — Plan Brief

> Full plan: `context/changes/llm-refactor/plan.md`
> Research: `context/changes/llm-refactor/research.md`

## What & Why

Refactor `backend/infrastructure/llm` so review instructions, structured-output schema, and product criteria for all annotation kinds live in **domain**, orchestration moves to **`AdrReviewService`**, and infrastructure becomes a thin **OpenAI SDK** transport. Today the prompt in `review_response.py` is out of sync with `required_sections.py` and `review_quality.py`, causing frequent validation retries — this refactor aligns what we tell the model with what we validate.

## Starting Point

S-04 shipped a working async review flow: `LlmReviewer` port, httpx-based OpenRouter/OpenAI-compatible adapters, `FakeReviewer`, and F-01 `validate_review_result` gate. Prompt, JSON parsing, HTTP, and `ReviewResult` mapping all sit in `infrastructure/llm/`. Structlog `llm.review.*` events are already on the httpx adapters (struct change complete).

## Desired End State

`AdrReviewService` builds messages from domain instructions, calls `LlmCompletionPort` (SDK client with strict JSON schema + fallback), maps `ReviewPayload` → `ReviewResult`. `RunAiReviewHandler` injects the service directly. Fake provider runs through the same service path. Legacy httpx reviewers and `LlmReviewer` port are removed. API and frontend unchanged; review quality should improve because prompts match domain rules.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Handler dependency | `AdrReviewService` directly | Clearer seam — handler orchestrates persistence, service owns review use case | Plan |
| `LlmReviewer` port | Remove | No facade needed when handler injects service | Plan |
| Structured output | Strict `json_schema` first, fallback `json_object` | Best quality on OpenRouter; graceful degradation for weaker endpoints | Plan |
| Annotation criteria | Explicit domain rules for all kinds + actionability | Prompt and validator stay in sync; section-scoped inconsistency/conciseness guidance | Plan |
| Transport | OpenAI Python SDK in infrastructure | Replaces duplicate httpx adapters; native Pydantic structured parse | Research / Plan |
| Fake provider | `FakeLlmCompletionPort` through service | Same parse/map path as production; heuristics move to fake port | Plan |
| Prompt versioning | Skip for now | Add when observability needs version correlation | Plan |
| Structlog | Migrate `llm.review.*` to SDK client | Struct change finished — preserve existing event names on new adapter | Plan |
| Service location | `application/services/adr_review_service.py` | Domain modules hold pure logic; service calls async I/O port | Research |

## Scope

**In scope:** Domain instructions/schema/actionability; `LlmCompletionPort`; OpenAI SDK client; `AdrReviewService`; handler/bootstrap/factory wiring; fake completion port; test updates; removal of legacy adapters; `openai` dependency.

**Out of scope:** Frontend, API contract changes, prompt versioning, new observability beyond migrating existing events, harness redesign, agent loops, re-review.

## Architecture / Approach

```
RunAiReviewHandler → AdrReviewService.review_adr(markdown)
  → build_review_system_prompt()          [domain]
  → LlmCompletionPort.complete_structured(ReviewPayload)  [application port]
  → to_review_result()                    [domain]
  → validate_review_result()              [application gate — unchanged]

OpenAiSdkCompletionClient / FakeLlmCompletionPort  [infrastructure]
```

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Domain review contract | Instructions, schema, actionability DRY; compat shim | Prompt wording — iterate against harness cases |
| 2. Thin completion transport | SDK client + fake port + structlog migration | Provider `json_schema` support varies — fallback path must work |
| 3. Service + handler wiring | `AdrReviewService`, bootstrap, test updates | Handler/API test mock paths |
| 4. Legacy cleanup | Delete httpx adapters, remove `LlmReviewer`, DRY validator | Missed import after deletion |

**Prerequisites:** None — builds on current main with structlog already landed.
**Estimated effort:** ~2–3 implementation sessions across 4 phases.

## Open Risks & Assumptions

- OpenRouter/Ollama may reject strict JSON schema on some models — fallback path is required and must be tested
- Longer system prompt increases token cost slightly — acceptable for MVP ADR sizes
- Explicit inconsistency/conciseness criteria are baseline heuristics — may need tuning after real OpenRouter runs
- `application/services/` is new — sets precedent for future application services in this repo

## Success Criteria (Summary)

- Prompt lists all five ADR sections and matches `validate_review_result` rules — fewer validation retries on complete ADRs
- Full `pytest` + ruff + ty green after each phase
- `LLM_PROVIDER=fake` dev flow unchanged from user perspective
- `llm.review.*` structlog events emitted from new SDK client
