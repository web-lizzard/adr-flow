# LLM Layer Refactor Implementation Plan

## Overview

Refactor `backend/infrastructure/llm` so review **semantics** (instructions, structured-output schema, actionability rules, product criteria for all annotation kinds) live in **domain**, **orchestration** lives in **`AdrReviewService`**, and **infrastructure** only handles transport via a thin `LlmCompletionPort` implemented with the **OpenAI Python SDK**. `RunAiReviewHandler` injects `AdrReviewService` directly (no `LlmReviewer` facade). External API, event flow, and frontend behavior stay unchanged.

## Current State Analysis

Today the LLM stack mixes concerns in infrastructure:

- `review_response.py` holds the system prompt, manual JSON parsing, and `ReviewResult` mapping
- `openrouter.py` and `openai_compatible.py` duplicate ~90% of HTTP + orchestration logic
- Domain section rules (`required_sections.py`) and runtime validation (`review_quality.py`) are **not reflected** in the prompt, causing frequent `validate_review_result` retries in `run_ai_review.py`
- Structlog events (`llm.review.request_started`, `http_completed`, `parsed`, `http_error`) already exist on the httpx adapters (struct change complete)

### Key Discoveries:

- Single LLM call site in application code: `run_ai_review.py:96` via `LlmReviewer.review(markdown)`
- `FakeReviewer` heuristics (`fake_reviewer.py:14-50`) are the only explicit criteria for `inconsistency` / `conciseness` — they should move into domain instructions and inform the fake completion port
- `application/services/` does not exist yet — first application service in this repo
- `openai` is not in `backend/pyproject.toml`; `httpx` is present and will remain as SDK transitive dep
- F-01 harness (`tests/review_quality/`) grades `ReviewResult` after mapping — wire models are generation contract only

## Desired End State

After this plan:

1. `build_review_system_prompt()` in domain lists all five `SectionName` values, placeholder rules, per-kind product criteria, and actionability requirements — synchronized with `validate_review_result`
2. `AdrReviewService.review_adr(markdown) -> ReviewResult` composes messages, calls `LlmCompletionPort`, parses `ReviewPayload`, maps to `ReviewResult`
3. `OpenAiSdkCompletionClient` is the sole HTTP adapter: `chat.completions.parse` with strict JSON schema, falling back to `json_object` + `ReviewPayload.model_validate_json` on provider errors
4. `FakeLlmCompletionPort` returns heuristic `ReviewPayload` JSON through the same service path as production
5. `RunAiReviewHandler` depends on `AdrReviewService`; `LlmReviewer` port and legacy httpx reviewer classes are removed
6. Structlog `llm.review.*` events live on the SDK client (same event names as today)
7. All existing API/handler/harness tests pass without behavioral regression

### Verification

- `cd backend && uv run pytest` — green
- `cd backend && uv run ruff check . && uv run ty check` — green
- Manual: `LLM_PROVIDER=fake just dev-backend`, submit ADR for review, annotations appear as before
- Optional manual with OpenRouter: review completes without validation retry loop on a complete ADR fixture

## What We're NOT Doing

- Frontend changes (polling, annotation UI unchanged)
- API contract changes (`submit-review`, `review-status`, response schemas)
- Prompt versioning (`REVIEW_INSTRUCTIONS_VERSION`) — deferred
- OpenTelemetry, metrics, or new observability beyond migrating existing `llm.review.*` structlog events
- LLM-as-judge or harness changes beyond using existing fixtures for schema unit tests
- Re-review after edit, streaming, or multi-turn agent loops
- Changes to `validate_review_result` gate semantics (still runs in handler after service returns)

## Implementation Approach

Incremental migration with a compat shim in phase 1 so existing adapters keep working until phase 4 deletion:

```
RunAiReviewHandler
    └── AdrReviewService.review_adr(markdown) -> ReviewResult
            ├── build_review_system_prompt()           # domain/adr/review_instructions.py
            ├── build_review_user_message(markdown)    # domain
            ├── LlmCompletionPort.complete_structured( # application port
            │       messages, response_model=ReviewPayload)
            └── to_review_result(payload, ...)         # domain/adr/review_llm_schema.py

OpenAiSdkCompletionClient (infrastructure/llm/openai_sdk_client.py)
    └── AsyncOpenAI(base_url, api_key).chat.completions.parse(...)
        └── fallback: json_object + model_validate_json on provider schema errors

FakeLlmCompletionPort (infrastructure/llm/fake_completion.py)
    └── heuristic ReviewPayload JSON (ported from current FakeReviewer logic)
```

Factory (`build_adr_review_service(settings)`) selects completion client by `LLM_PROVIDER` and returns configured `AdrReviewService`.

## Critical Implementation Details

- **Pydantic in domain:** `ReviewPayload` / `ReviewAnnotationPayload` live in `domain/adr/review_llm_schema.py` with `Field(description=...)`. They are wire/generation models, not replacements for `ReviewResult` / `ReviewAnnotation` value objects used in events and projections.
- **Structured-output fallback:** On `OpenAI` API errors indicating unsupported `json_schema` / `strict` mode, retry once with `response_format={"type": "json_object"}` and parse via `ReviewPayload.model_validate_json`. Log fallback at WARNING with `llm.review.structured_output_fallback`.
- **Handler tests:** Replace inline `FakeLlmReviewer` with `FakeAdrReviewService` (returns preset `ReviewResult`) to keep handler tests focused on retry/idempotency/persistence — service gets its own tests with `FakeLlmCompletionPort`.
- **API integration tests:** Update patches from `build_llm_reviewer` to `build_adr_review_service` in `test_adr_api.py`.

## Phase 1: Domain Review Contract

### Overview

Establish domain as source of truth for review instructions, wire schema, actionability rules, and payload→VO mapping. Keep legacy adapters working via a thin shim.

### Changes Required:

#### 1. Shared actionability rules

**File**: `backend/domain/adr/review_actionability.py`

**Intent**: Extract kind-specific field requirements currently duplicated in `application/review_quality.py` so both the system prompt and runtime validator reference the same rules.

**Contract**: Module exports rules or helper functions describing required fields per `ReviewAnnotationKind` (`missing_section`: message + suggestion; `inconsistency`: message + location; `conciseness`: message + suggestion + location). No application/infrastructure imports.

#### 2. Review instructions

**File**: `backend/domain/adr/review_instructions.py`

**Intent**: Build the system prompt from domain constants — all five `SectionName` / `REQUIRED_SECTION_HEADINGS`, empty-body and placeholder (`tbd`/`todo`/`n/a`) rules, one `missing_section` annotation per gap, and explicit product criteria for `inconsistency` and `conciseness` (section-scoped, actionable). Criteria should reflect current `FakeReviewer` heuristics as baseline product rules, expressed as instructions to the model rather than code branches.

**Contract**: `build_review_system_prompt() -> str` includes every `SectionName.value` and actionability requirements from `review_actionability`. `build_review_user_message(markdown: str) -> str` wraps ADR markdown for the user role.

#### 3. Wire schema and mapping

**File**: `backend/domain/adr/review_llm_schema.py`

**Intent**: Define Pydantic wire models with `Field(description=...)` for structured output and map validated payloads to domain `ReviewResult`.

**Contract**: `ReviewAnnotationPayload`, `ReviewPayload` models; `to_review_result(payload: ReviewPayload, *, markdown: str, reviewed_at: datetime) -> ReviewResult` raises domain-appropriate errors on invalid kinds/fields (or rely on Pydantic validation before mapping).

#### 4. Domain exports and tests

**File**: `backend/domain/adr/__init__.py` (if re-exports needed)

**Intent**: Export new public symbols following existing `domain/adr` conventions.

**Contract**: Only export what application/infrastructure need; keep module surface minimal.

#### 5. Unit tests

**Files**: `backend/tests/domain/adr/test_review_instructions.py`, `backend/tests/domain/adr/test_review_llm_schema.py`

**Intent**: Verify prompt contains all section names and placeholder rules; verify `ReviewPayload.model_validate_json` accepts/rejects shapes using harness fixture JSON where applicable; verify `to_review_result` round-trips with `validate_review_result` on synthetic cases from `tests/review_quality/cases.py`.

**Contract**: No HTTP or OpenAI SDK in domain tests.

#### 6. Compat shim (temporary)

**File**: `backend/infrastructure/llm/review_response.py`

**Intent**: Delegate `review_system_prompt()` to `build_review_system_prompt()` and route parsing through `ReviewPayload` + `to_review_result` so phase 1 does not break existing adapters.

**Contract**: Public function signatures unchanged until phase 4 deletion.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/domain/adr/test_review_instructions.py tests/domain/adr/test_review_llm_schema.py` — pass
- `cd backend && uv run pytest tests/infrastructure/llm/` — pass (shim preserves adapter behavior)
- `cd backend && uv run ruff check . && uv run ty check` — pass

#### Manual Verification:

- Inspect `build_review_system_prompt()` output — all five sections, placeholder rules, and per-kind criteria are present and readable

**Implementation Note**: Pause for manual confirmation before phase 2.

---

## Phase 2: Thin Completion Transport

### Overview

Introduce `LlmCompletionPort`, implement OpenAI SDK client with structured-output fallback, and add fake completion port. Migrate structlog events from legacy adapters to the new client.

### Changes Required:

#### 1. Completion port

**File**: `backend/application/ports/llm_completion.py`

**Intent**: Define a transport-only port with no ADR knowledge.

**Contract**: `LlmCompletionPort` protocol with `async def complete_structured(self, *, messages: list[ChatMessage], response_model: type[T]) -> T` where `T` is a Pydantic `BaseModel`. `ChatMessage` is a simple typed dict or dataclass `{role, content}`.

#### 2. OpenAI SDK client

**File**: `backend/infrastructure/llm/openai_sdk_client.py`

**Intent**: Single HTTP adapter replacing `openrouter.py` and `openai_compatible.py`. Uses `AsyncOpenAI(base_url=..., api_key=...)`.

**Contract**: Implements `LlmCompletionPort`. Primary path: `client.chat.completions.parse(..., response_format=response_model)`. Fallback on provider schema errors: `json_object` + `response_model.model_validate_json(content)`. Raises `LlmProviderError` on HTTP/API failures, `LlmParseError` on unparseable content. Emits structlog events: `llm.review.request_started`, `llm.review.http_completed`, `llm.review.parsed`, `llm.review.http_error`, plus `llm.review.structured_output_fallback` on fallback. Fields: `provider`, `model`, `markdown_length` (from user message), `duration_ms`, `status_code` where applicable. No secrets or full markdown in logs.

#### 3. Fake completion port

**File**: `backend/infrastructure/llm/fake_completion.py`

**Intent**: Deterministic dev/test transport that returns `ReviewPayload` built from heuristics (ported from `fake_reviewer.py`), so the fake path exercises the same parse/map pipeline as production.

**Contract**: Implements `LlmCompletionPort`; ignores messages or validates they were sent; returns heuristic `ReviewPayload` as parsed model.

#### 4. Dependency

**File**: `backend/pyproject.toml`, `backend/uv.lock`

**Intent**: Add `openai` package respecting `exclude-newer = "7 days"`.

**Contract**: Run `uv lock` after adding dependency.

#### 5. Adapter tests

**Files**: `backend/tests/infrastructure/llm/test_openai_sdk_client.py` (new), update/remove `test_openrouter.py` and `test_openai_compatible.py` in phase 4

**Intent**: Test SDK client via injected mock `AsyncOpenAI` or custom HTTP client; cover success, auth headers, provider error, parse error, and structured-output fallback path.

**Contract**: Tests target `OpenAiSdkCompletionClient`, not deleted reviewer classes.

#### 6. Fake completion tests

**File**: `backend/tests/infrastructure/llm/test_fake_completion.py`

**Intent**: Verify fake port returns valid `ReviewPayload` for known markdown inputs (missing sections, long body, decision/status present).

**Contract**: No network.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/infrastructure/llm/test_openai_sdk_client.py tests/infrastructure/llm/test_fake_completion.py` — pass
- `cd backend && uv run ruff check . && uv run ty check` — pass

#### Manual Verification:

- None required — transport not yet wired to handler

**Implementation Note**: Pause before phase 3.

---

## Phase 3: AdrReviewService and Handler Wiring

### Overview

Centralize review orchestration in `AdrReviewService`, wire bootstrap/factory, and switch the handler to inject the service directly. Remove `LlmReviewer` from the handler dependency chain.

### Changes Required:

#### 1. Review service

**File**: `backend/application/services/adr_review_service.py`

**Intent**: Own the review use case: build messages from domain instructions, call `LlmCompletionPort.complete_structured(..., response_model=ReviewPayload)`, map to `ReviewResult` via `to_review_result`.

**Contract**: `async def review_adr(self, markdown: str) -> ReviewResult`. Raises `LlmParseError` / `LlmProviderError` from port unchanged. Sets `reviewed_at` at mapping time.

#### 2. Factory

**File**: `backend/infrastructure/llm/factory.py`

**Intent**: Replace `build_llm_reviewer` with `build_adr_review_service(settings) -> AdrReviewService`.

**Contract**: `fake` → `FakeLlmCompletionPort`; `openrouter` → `OpenAiSdkCompletionClient` with default OpenRouter base URL and required API key; `openai_compatible` → SDK client with `settings.llm_base_url` (required). Log `llm.reviewer_built` with `provider` and `model` (rename event to `llm.review_service_built` if cleaner — optional, not required).

#### 3. Bootstrap

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Wire `AdrReviewService` into `RunAiReviewHandler`.

**Contract**: Replace `llm_reviewer = build_llm_reviewer(...)` with `adr_review_service = build_adr_review_service(...)`; pass to handler constructor.

#### 4. Handler

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Depend on `AdrReviewService` instead of `LlmReviewer`; call `review_adr(markdown)`.

**Contract**: Constructor parameter `adr_review_service: AdrReviewService`. Retry, idempotency, and `validate_review_result` logic unchanged.

#### 5. Handler tests

**File**: `backend/tests/application/handlers/test_run_ai_review.py`

**Intent**: Replace `FakeLlmReviewer` with `FakeAdrReviewService` returning preset `ReviewResult` lists.

**Contract**: Same test scenarios (success, validation retry, terminal failure, idempotency skips).

#### 6. Service tests

**File**: `backend/tests/application/services/test_adr_review_service.py`

**Intent**: Test orchestration with fake `LlmCompletionPort` returning valid/invalid `ReviewPayload`; verify mapping and error propagation.

**Contract**: No real HTTP.

#### 7. API integration tests

**File**: `backend/tests/infrastructure/api/test_adr_api.py`

**Intent**: Update mocks from `build_llm_reviewer` to `build_adr_review_service`.

**Contract**: End-to-end submit-review → poll → after_review flows still pass.

#### 8. Test app conftest

**File**: `backend/tests/infrastructure/api/conftest.py`

**Intent**: Ensure test settings still use `llm_provider="fake"` through new factory path.

**Contract**: No production code paths broken for test app creation.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/application/handlers/test_run_ai_review.py tests/application/services/test_adr_review_service.py` — pass
- `cd backend && uv run pytest tests/infrastructure/api/test_adr_api.py` — pass
- `cd backend && uv run pytest` — full suite green
- `cd backend && uv run ruff check . && uv run ty check` — pass

#### Manual Verification:

- `just dev-backend` with `LLM_PROVIDER=fake`: submit complete ADR → `after_review` with annotations
- Submit ADR with missing sections → `missing_section` annotations for each gap

**Implementation Note**: Pause for manual confirmation before phase 4.

---

## Phase 4: Legacy Cleanup and DRY

### Overview

Remove superseded files, DRY `review_quality` with domain actionability, and ensure full regression clean.

### Changes Required:

#### 1. DRY review quality validator

**File**: `backend/application/review_quality.py`

**Intent**: Import actionability field requirements from `domain/adr/review_actionability.py` instead of inline duplication.

**Contract**: `validate_review_result` behavior unchanged — existing `tests/application/test_review_quality.py` and harness tests pass without modification.

#### 2. Delete legacy LLM files

**Files to remove**:

- `backend/infrastructure/llm/review_response.py`
- `backend/infrastructure/llm/openrouter.py`
- `backend/infrastructure/llm/openai_compatible.py`
- `backend/infrastructure/llm/fake_reviewer.py`
- `backend/application/ports/llm_reviewer.py`

**Intent**: Remove dead code after service wiring is complete.

**Contract**: No remaining imports of deleted modules.

#### 3. Delete legacy tests

**Files to remove/update**:

- `backend/tests/infrastructure/llm/test_openrouter.py`
- `backend/tests/infrastructure/llm/test_openai_compatible.py`

**Intent**: Coverage lives in SDK client and service tests.

#### 4. Update architecture doc reference (optional minor)

**File**: `context/foundation/application-architecture.md`

**Intent**: Replace `LlmReviewer` mention with `AdrReviewService` + `LlmCompletionPort` if implementer touches this file during cleanup. Skip if not already editing.

**Contract**: Doc reflects new port names.

#### 5. Change metadata

**File**: `context/changes/llm-refactor/change.md`

**Intent**: Set `status: planned`, `updated: 2026-06-18`.

**Contract**: Frontmatter accurate.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest` — full suite green
- `cd backend && uv run ruff check . && uv run ty check` — pass
- `rg "LlmReviewer|openrouter\.py|review_response|FakeReviewer" backend/` — no hits outside archive/comments

#### Manual Verification:

- With `LLM_PROVIDER=openrouter` and valid API key (if available): submit review on complete ADR fixture — succeeds without validation retry loop
- Cloud Logging query: `llm.review.*` events appear from SDK client on review submit

**Implementation Note**: Final manual sign-off before `/archive`.

---

## Testing Strategy

### Unit Tests:

- Domain: prompt content, schema validation, `to_review_result` mapping
- SDK client: HTTP errors, parse errors, structured-output fallback
- Fake completion: heuristic payload shapes
- Service: message assembly + port delegation
- Handler: retry/idempotency unchanged

### Integration Tests:

- API submit-review flow with mocked `build_adr_review_service`
- Event bus + dispatcher with `llm_provider=fake` (existing `test_task_group_bus.py`)

### Harness Parity:

- Run synthetic cases from `tests/review_quality/cases.py` through `to_review_result` + `validate_review_result` after mapping

### Manual Testing Steps:

1. Start `just dev-backend` with `LLM_PROVIDER=fake`
2. Create ADR, fill all sections, submit for review — expect `after_review` + annotations
3. Create ADR with `## Context` only — expect five `missing_section` annotations
4. (Optional) OpenRouter: complete ADR from harness fixtures — no double retry in logs

## Performance Considerations

- Structured `json_schema` may add negligible latency vs `json_object`; fallback adds one extra round-trip only on unsupported providers
- No change to async event-bus polling or handler concurrency model
- Prompt will be longer (more domain rules) — monitor token usage; acceptable for MVP ADR sizes

## Migration Notes

- No database migration
- Deploy: no new required env vars; existing `LLM_*` settings unchanged
- `openai` becomes a direct dependency; lockfile refresh required
- Rollback: revert commit — old adapters restored from git if needed before phase 4 merge

## References

- Research: `context/changes/llm-refactor/research.md`
- Prior implementation: `context/archive/2026-06-17-first-ai-review-annotations/plan.md`
- Quality gate: `context/archive/2026-06-16-review-quality-checks/research.md`
- Structlog (complete): `context/changes/struct/plan-brief.md`
- `backend/infrastructure/llm/review_response.py:16-22` — prompt to replace
- `backend/application/handlers/run_ai_review.py:96` — call site to rewire
- `backend/domain/adr/required_sections.py:6-89` — section source of truth

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Domain Review Contract

#### Automated

- [x] 1.1 `pytest tests/domain/adr/test_review_instructions.py tests/domain/adr/test_review_llm_schema.py` — pass — fdcb1ad
- [x] 1.2 `pytest tests/infrastructure/llm/` — pass (shim preserves adapter behavior) — fdcb1ad
- [x] 1.3 `ruff check . && ty check` — pass — fdcb1ad

#### Manual

- [x] 1.4 Inspect `build_review_system_prompt()` — all sections, placeholders, per-kind criteria present

### Phase 2: Thin Completion Transport

#### Automated

- [x] 2.1 `pytest tests/infrastructure/llm/test_openai_sdk_client.py tests/infrastructure/llm/test_fake_completion.py` — pass — 090e33d
- [x] 2.2 `ruff check . && ty check` — pass — 090e33d

### Phase 3: AdrReviewService and Handler Wiring

#### Automated

- [x] 3.1 `pytest tests/application/handlers/test_run_ai_review.py tests/application/services/test_adr_review_service.py` — pass — 0af4662
- [x] 3.2 `pytest tests/infrastructure/api/test_adr_api.py` — pass — 0af4662
- [x] 3.3 Full `pytest` suite — green — 0af4662
- [x] 3.4 `ruff check . && ty check` — pass — 0af4662

#### Manual

- [x] 3.5 `LLM_PROVIDER=fake` — submit complete ADR → `after_review` with annotations — 0af4662
- [x] 3.6 Submit ADR with missing sections → one `missing_section` per gap — 0af4662

### Phase 4: Legacy Cleanup and DRY

#### Automated

- [x] 4.1 Full `pytest` suite — green
- [x] 4.2 `ruff check . && ty check` — pass
- [x] 4.3 No stale imports of removed modules (`rg` check)

#### Manual

- [x] 4.4 (Optional) OpenRouter — complete ADR without validation retry loop
- [x] 4.5 `llm.review.*` structlog events visible from SDK client
