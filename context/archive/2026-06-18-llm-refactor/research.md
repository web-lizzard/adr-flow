---
date: 2026-06-18T12:00:00+00:00
researcher: Cursor Agent
git_commit: 052a7860b12bfe74ac8db2b6b9b73fda4b450482
branch: main
repository: adr-flow
topic: "Refactor backend/infrastructure/llm — domain instructions, structured output, thin adapters"
tags: [research, codebase, llm, domain, structured-output, hexagonal, adr-review]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
last_updated_note: "Added follow-up: OpenAI Python SDK as adapter transport"
---

# Research: Refactor backend/infrastructure/llm

**Date**: 2026-06-18
**Researcher**: Cursor Agent
**Git Commit**: `052a7860b12bfe74ac8db2b6b9b73fda4b450482`
**Branch**: main
**Repository**: adr-flow

## Research Question

Jak zrefaktorować `backend/infrastructure/llm`, aby:

1. Przenieść instrukcje (prompty) do domeny jako ważny element systemu.
2. Dodać modele structured output (Pydantic) z `Field(..., description=...)`, wykorzystywane przez LLM.
3. Uczynić serwisy LLM jak najlżejszymi — domena (lub warstwa aplikacji oparta na domenie) wystawia serwis korzystający z providera; logika biznesowa poza adapterami HTTP.

## Summary

Dziś warstwa LLM w infrastrukturze robi za dużo: **prompt**, **parsowanie JSON**, **wywołanie HTTP** i **mapowanie na `ReviewResult`** siedzą w `infrastructure/llm/`, podczas gdy reguły jakości review (sekcje, actionability) są rozproszone między `domain/adr/required_sections.py`, `application/review_quality.py` i luźnym tekstem promptu w `review_response.py`.

**Rekomendowany kierunek refaktoru:**

| Cel | Gdzie | Co |
|-----|-------|-----|
| Instrukcje review | `domain/adr/review_instructions.py` | Czyste funkcje/stałe budujące system prompt z `SectionName`, `REQUIRED_SECTION_HEADINGS`, reguł placeholderów i actionability |
| Structured output schema | `domain/adr/review_llm_schema.py` | Pydantic modele wire (`ReviewAnnotationPayload`, `ReviewPayload`) z `Field(description=...)`; `model_json_schema()` dla providera |
| Mapowanie wire → domain | `domain/adr/review_llm_schema.py` lub `domain/adr/review_mapping.py` | `to_review_result(payload, *, markdown, reviewed_at) -> ReviewResult` |
| Serwis review (logika biznesowa) | `application/services/adr_review_service.py` | Składa prompt, woła port, mapuje wynik; handler tylko orkiestruje persystencję |
| Cienki port providera | `application/ports/llm_completion.py` | `complete(messages, *, response_format) -> str` — bez wiedzy o ADR |
| Adaptery HTTP | `infrastructure/llm/` | Tylko transport (`httpx`), błędy sieci, ekstrakcja `content` z body OpenAI-compatible |
| Usunąć duplikację | `infrastructure/llm/chat_completions.py` | Jeden wspólny adapter zamiast `openrouter.py` + `openai_compatible.py` (~90% copy-paste) |

**Port `LlmReviewer.review(markdown) -> ReviewResult`** może zostać jako fasada (implementacja deleguje do `AdrReviewService` + `LlmCompletionPort`) albo zostać zastąpiony w handlerze bezpośrednim wstrzyknięciem serwisu.

**Uwaga architektoniczna:** Historycznie S-04 zakładało „prompt w infrastructure” (`context/changes/first-ai-review-annotations/plan.md`). Przeniesienie **treści instrukcji** do domeny jest świadomą zmianą — domena nadal **nie** importuje `httpx` ani providerów; trzyma **semantykę review**, nie transport.

## Detailed Findings

### Stan obecny — podział odpowiedzialności

#### Infrastructure (`backend/infrastructure/llm/`)

| Plik | Odpowiedzialność | Linie kluczowe |
|------|------------------|----------------|
| `review_response.py` | System prompt, parsowanie JSON, mapowanie na `ReviewAnnotation`/`ReviewResult` | `13-23` prompt, `26-54` parse, `81-107` annotation mapping |
| `openrouter.py` | HTTP POST, `response_format: json_object`, orchestracja review | `35-85` |
| `openai_compatible.py` | Identyczny pipeline jak OpenRouter | `33-83` |
| `fake_reviewer.py` | Deterministyczny reviewer (używa `find_missing_or_empty_sections`) | `14-50` |
| `factory.py` | Wybór providera z `Settings` | `10-33` |
| `errors.py` | `LlmProviderError`, `LlmParseError` | `4-9` |

#### Application

| Plik | Odpowiedzialność |
|------|------------------|
| `ports/llm_reviewer.py:8-9` | Port: `review(markdown) -> ReviewResult` |
| `handlers/run_ai_review.py:52-67` | Retry, idempotency, wywołanie portu, `validate_review_result` |
| `review_quality.py:23-124` | Post-LLM: pokrycie sekcji, actionability |

#### Domain

| Plik | Odpowiedzialność |
|------|------------------|
| `required_sections.py:6-89` | Pięć sekcji, parser markdown, `find_missing_or_empty_sections`, placeholdery `tbd/todo/n/a` |
| `value_objects.py:51-71` | `ReviewAnnotationKind`, `ReviewAnnotation`, `ReviewResult` |
| `errors.py:18-23` | `InvalidReviewAnnotation`, `InvalidReviewResult` — **nieużywane** przez parser LLM |

#### Bootstrap

```83:110:backend/infrastructure/bootstrap.py
    llm_reviewer = build_llm_reviewer(settings)
    ...
    run_ai_review_handler = RunAiReviewHandler(
        uow_factory,
        adr_repository,
        llm_reviewer,
    )
```

### Problem 1 — instrukcje poza domeną i niezsynchronizowane z regułami

Obecny prompt (`review_response.py:13-18`):

```python
_REVIEW_SYSTEM_PROMPT = (
    "You review Architecture Decision Records (ADRs). "
    "Return JSON with an annotations array. ..."
)
```

**Czego brakuje względem domeny:**

| Reguła domeny | Źródło | W prompcie? |
|---------------|--------|-------------|
| Dokładnie 5 sekcji: Context, Options, Decision, Status, Consequences | `required_sections.py:6-20` | Nie |
| Nagłówki `## Context` itd. (case-sensitive) | `required_sections.py:6-12`, `61-63` | Nie |
| Pusta treść = brak sekcji | `required_sections.py:83` | Nie |
| Placeholdery `tbd`/`todo`/`n/a` = brak | `required_sections.py:28,88-89` | Nie |
| Jedna adnotacja `missing_section` na każdą lukę | `review_quality.py:98-99` | Nie |
| Kryteria `inconsistency` / `conciseness` | tylko enum w `value_objects.py:51-54` | Nie (tylko kształt JSON) |

Skutek: LLM zwraca JSON zgodny ze składnią, ale **retry w handlerze** (`run_ai_review.py:55-59`) często odrzuca wynik przez `validate_review_result`.

**Rekomendacja (cel 1):** `domain/adr/review_instructions.py`:

- `def build_review_system_prompt() -> str` — składa tekst z `SectionName`, `REQUIRED_SECTION_HEADINGS`, `_PLACEHOLDER_TOKENS` (wyeksportowany lub duplikat jako stała publiczna).
- `def build_review_user_message(markdown: str) -> str` — opcjonalnie opakowuje ADR z kontekstem (np. „Review the following ADR markdown”).
- Współdzielone reguły actionability z `review_quality.py` — wyciągnąć do `domain/adr/review_actionability.py` lub tabeli w `review_instructions.py`, importowanej zarówno przez prompt, jak i validator.

Domena **nie** zna `response_format` ani endpointów — tylko **co** model ma ocenić i **jak** opisać pola.

### Problem 2 — brak structured output z opisami pól

Dziś adaptery używają ogólnego `response_format: {"type": "json_object"}` (`openrouter.py:45`, `openai_compatible.py:44`), a kształt JSON jest opisany wyłącznie w system prompt (tekst).

**Rekomendacja (cel 2):** modele Pydantic w domenie (wire shape, nie event payload):

```python
# domain/adr/review_llm_schema.py (propozycja)
class ReviewAnnotationPayload(BaseModel):
    kind: ReviewAnnotationKind = Field(
        description="Annotation category: missing_section, inconsistency, or conciseness."
    )
    message: str = Field(description="Human-readable issue description.")
    location: str | None = Field(
        default=None,
        description="Markdown heading, e.g. '## Context'. Required for inconsistency and conciseness.",
    )
    suggestion: str | None = Field(
        default=None,
        description="Concrete fix. Required for missing_section and conciseness.",
    )

class ReviewPayload(BaseModel):
    annotations: list[ReviewAnnotationPayload] = Field(
        description="All actionable review findings for this ADR."
    )
```

- `ReviewPayload.model_json_schema()` → `response_format` dla OpenAI-compatible API (`json_schema` tam gdzie provider wspiera; fallback `json_object` + ten sam schema w prompcie dla Ollama lokalnie).
- Mapowanie: `ReviewPayload` → `ReviewResult` (dodaje `reviewed_at`, `reviewed_content` po stronie aplikacji/adaptera — **nie** z LLM).

**`ReviewAnnotation` / `ReviewResult` w `value_objects.py` pozostają kanonicznym modelem domenowym** (eventy, projekcje). Modele payload są **kontraktem generacji**, nie zastępują VO.

### Problem 3 — adaptery zbyt grube; logika biznesowa w infrastructure

`OpenRouterReviewer.review()` i `OpenAiCompatibleReviewer.review()` robią wszystko:

1. Budują messages z `review_system_prompt()`
2. Wywołują HTTP
3. Parsują JSON
4. Budują `ReviewResult`

To łączy **transport** z **use case review ADR**.

**Rekomendacja (cel 3) — docelowa architektura:**

```
RunAiReviewHandler
    └── AdrReviewService.review_adr(markdown) -> ReviewResult
            ├── build_review_system_prompt()          # domain
            ├── ReviewPayload.model_json_schema()     # domain
            ├── LlmCompletionPort.complete(...)       # application port
            └── ReviewPayload → ReviewResult          # domain mapper

ChatCompletionsClient (infrastructure)
    └── POST /chat/completions, extract content, raise LlmProviderError
```

**`AdrReviewService`** (application — bo woła port; alternatywnie „domain service” w `domain/adr/services/` jeśli wstrzyknięcie portu przez aplikację):

- Składa `messages`
- Przekazuje schema jako `format`
- Parsuje JSON do `ReviewPayload` (Pydantic `model_validate_json`)
- Mapuje na `ReviewResult`
- Rzuca `LlmParseError` / deleguje błędy providera

**`FakeReviewer`:** przenieść do `infrastructure/llm/fake_completion.py` jako fake portu **albo** zostawić jako implementację `LlmReviewer` delegującą do tego samego `AdrReviewService` z mock portem — lepiej: fake bez HTTP, ale nadal przez serwis (spójność ścieżek).

### Duplikacja OpenRouter vs OpenAI-compatible

`openrouter.py` i `openai_compatible.py` różnią się tylko:

- domyślny `base_url` (`openrouter.py:16`)
- wymagalność `api_key` (`openrouter.py:29` vs `openai_compatible.py:28`)

Reszta identyczna. **Jeden** `ChatCompletionsClient` z konfiguracją:

```python
@dataclass(frozen=True)
class ChatCompletionsConfig:
    base_url: str
    api_key: str | None
    model: str
    timeout_seconds: float
    provider_label: str  # do logów
```

### Granice warstw po refaktorze

| Warstwa | Zawiera | Nie zawiera |
|---------|---------|-------------|
| `domain/adr/` | Instrukcje, schema payload, mapowanie payload→VO, `SectionName`, parser | `httpx`, API keys, `response_format` provider-specific |
| `application/` | `AdrReviewService`, `LlmCompletionPort`, handler, `validate_review_result` | HTTP, OpenRouter URL |
| `infrastructure/llm/` | HTTP client, factory, `FakeCompletion`, ekstrakcja `choices[0].message.content` | Prompt text, reguły sekcji ADR |

Zgodne z `application-architecture.md` i `backend-architecture.mdc`: domena bez HTTP; porty w application; adaptery cienkie.

## Proponowany układ plików

```
backend/
  domain/adr/
    review_instructions.py      # NEW — build_review_system_prompt(), actionability copy
    review_llm_schema.py        # NEW — ReviewPayload, Field descriptions, to_review_result()
    required_sections.py        # istniejący — source of truth sekcji
    value_objects.py            # bez zmian semantycznych ReviewResult
  application/
    ports/
      llm_completion.py         # NEW — thin completion port
      llm_reviewer.py           # DEPRECATE lub fasada → AdrReviewService
    services/
      adr_review_service.py     # NEW — orchestracja review + mapowanie
    handlers/run_ai_review.py   # używa AdrReviewService zamiast grubego portu
    review_quality.py           # import reguł actionability z domeny (DRY z promptem)
  infrastructure/llm/
    chat_completions.py         # NEW — wspólny HTTP adapter
    completion_client.py        # implements LlmCompletionPort
    factory.py                  # buduje CompletionClient + AdrReviewService → LlmReviewer facade
    fake_completion.py          # opcjonalnie
    errors.py                   # bez zmian
    review_response.py          # USUNĄĆ po migracji (prompt + parse)
    openrouter.py               # USUNĄĆ — zastąpione przez chat_completions
    openai_compatible.py        # USUNĄĆ
```

## Code References

- `backend/infrastructure/llm/review_response.py:13-23` — prompt w infrastructure (do przeniesienia)
- `backend/infrastructure/llm/review_response.py:26-107` — ręczne parsowanie JSON (zastąpić Pydantic `ReviewPayload`)
- `backend/infrastructure/llm/openrouter.py:35-85` — gruby adapter review
- `backend/infrastructure/llm/openai_compatible.py:33-83` — duplikat OpenRouter
- `backend/infrastructure/llm/fake_reviewer.py:14-50` — fake z logiką heurystyczną
- `backend/infrastructure/llm/factory.py:10-33` — factory providerów
- `backend/application/ports/llm_reviewer.py:8-9` — obecny port
- `backend/application/handlers/run_ai_review.py:52-67` — retry + walidacja
- `backend/application/review_quality.py:84-124` — reguły jakości (DRY z promptem)
- `backend/domain/adr/required_sections.py:6-89` — source of truth sekcji
- `backend/domain/adr/value_objects.py:51-71` — kanoniczne VO review
- `backend/infrastructure/bootstrap.py:83-110` — wiring LLM → handler

## Architecture Insights

### Zgodność z hexagonem i świadome odchylenie od S-04

- S-04 planował prompt w `infrastructure/llm/` i port `markdown -> ReviewResult`.
- Refaktor **zachowuje** cienki port transportowy i **przenosi semantykę** (instrukcje, schema) do domeny — to nie łamie reguły „domain bez HTTP”, bo instrukcje to czysta logika biznesowa produktu (jak `required_sections.py`).
- `validate_review_result` zostaje w application jako **runtime gate** przed zapisem; może importować te same reguły co prompt.

### Structured output a provider

- OpenAI-compatible: `response_format: { type: "json_schema", json_schema: { schema: ReviewPayload.model_json_schema(), strict: true } }` tam gdzie wspierane.
- Ollama lokalnie: `format: ReviewPayload.model_json_schema()` (z poprzedniego researchu Exa).
- Ollama Cloud / słabsze endpointy: fallback — schema w prompcie + `json_object` (bez zmiany modeli domenowych).
- `Field(description=...)` trafia do JSON Schema `description` — wspiera constrained decoding i dokumentację dla modelu.

### Testy

- Unit: `build_review_system_prompt()` zawiera wszystkie `SectionName.value`.
- Unit: `ReviewPayload.model_validate_json` na fixture z harnessu (`backend/tests/review_quality/fixtures/`).
- Parity: `to_review_result` + `validate_review_result` na synthetic cases z `cases.py`.
- Integration: istniejące testy API/handlerów bez zmiany zachowania zewnętrznego (`test_adr_api.py`, `test_dispatcher.py`).
- Usunąć zależność testów od `review_response.parse_review_payload` jeśli plik zniknie.

## Historical Context (from prior changes)

- `context/changes/first-ai-review-annotations/research.md` — ustalono port `LlmReviewer`, adapter w infrastructure, F-01 jako brama jakości.
- `context/changes/first-ai-review-annotations/plan.md:246-254` — adapter ma „request structured JSON, parse into ReviewResult” — refaktor realizuje to przez Pydantic schema zamiast ręcznego parse.
- `context/archive/2026-06-16-review-quality-checks/research.md` — F-01 nie wymyśla osobnego kontraktu JSON; grades `ReviewResult` — **nadal aktualne** po mapowaniu z `ReviewPayload`.
- `context/archive/2026-06-16-review-quality-checks/research.md:167` — S-04 miał „own prompt configuration” w infrastructure; ten change **przesuwa treść promptu** do domeny.
- `context/changes/struct/research.md` — planowane logi `llm.review.*` w adapterach HTTP; po refaktorze logować w `ChatCompletionsClient`, nie w `AdrReviewService`.

## Related Research

- `context/changes/first-ai-review-annotations/research.md` — pierwotny kształt portu i async flow
- `context/archive/2026-06-16-review-quality-checks/research.md` — harness i kontrakt `ReviewResult`
- `context/changes/struct/research.md` — observability LLM (osobny change — structlog)

## Open Questions

1. **Gdzie dokładnie „serwis domenowy”:** `application/services/adr_review_service.py` (woła port) vs `domain/adr/review_service.py` (czyste funkcje + port wstrzykiwany w application)? Rekomendacja: **application service** + **domain modules** (instructions, schema, mapowanie) — czysty domain nie powinien zależeć od portu async I/O.
2. **Czy zachować `LlmReviewer` jako publiczny port** dla bootstrap/testów, czy handler wstrzykuje `AdrReviewService` bezpośrednio?
3. **`json_schema` strict vs `json_object`:** czy factory ma wybierać format per `settings.llm_provider`?
4. **Wersjonowanie promptu:** dodać `REVIEW_INSTRUCTIONS_VERSION: str` w domenie dla logów (`struct` change)?
5. **Reguły `inconsistency` / `conciseness`:** czy dopisać do domeny produktowe kryteria (obecnie tylko stub w `FakeReviewer`), czy zostawić jako „model discretion” z actionability gate?
6. **Relacja z change `struct`:** refaktor LLM i structlog można robić równolegle; logi przenieść na nowy `ChatCompletionsClient`.

## Rekomendowany plan implementacji (fazy)

| Faza | Zakres | Ryzyko |
|------|--------|--------|
| **1** | `review_instructions.py` + `review_llm_schema.py`; podmiana importów w `review_response.py` (kompat shim) | Niskie |
| **2** | `LlmCompletionPort` + `ChatCompletionsClient`; scalenie OpenRouter/OpenAI | Średnie |
| **3** | `AdrReviewService`; factory zwraca fasadę `LlmReviewer` | Średnie |
| **4** | Usunięcie `review_response.py`, starych adapterów; DRY `review_quality` ↔ instructions | Niskie |
| **5** | `response_format: json_schema` + testy na fixture harnessu | Zależne od providera |

## Follow-up Research 2026-06-18 — OpenAI Python SDK jako adapter transportu

### Pytanie

Czy zamiast ręcznego `httpx.post` + `extract_json_content` warto użyć oficjalnego **OpenAI Python SDK** (`openai`) w adapterze infrastructure?

### Odpowiedź

**Tak — to dobry pomysł** i dobrze wpisuje się w refaktor `llm-refactor`, o ile SDK zostaje **wyłącznie w infrastructure** i implementuje cienki port `LlmCompletionPort`, a nie zastępuje `AdrReviewService`.

### Dlaczego to pasuje

| Aspekt | Dziś (`httpx`) | Z OpenAI SDK |
|--------|----------------|--------------|
| Structured output | Ręczne `response_format: {"type": "json_object"}` + `json.loads` + `parse_review_payload` | `client.chat.completions.parse(..., response_format=ReviewPayload)` → `message.parsed` |
| JSON Schema | Trzeba samemu budować `json_schema` + `strict` | SDK konwertuje Pydantic → `json_schema` ze `strict: True` ([openai-python helpers](https://github.com/openai/openai-python/blob/main/helpers.md)) |
| OpenRouter / Ollama / lokalny endpoint | `httpx` + własny URL | `AsyncOpenAI(base_url=..., api_key=...)` — ten sam klient, różne `Settings` |
| Duplikacja adapterów | `openrouter.py` + `openai_compatible.py` | Jeden `OpenAiSdkCompletionClient` w `infrastructure/llm/` |
| Testy | `httpx.MockTransport` | `openai` wspiera custom `http_client` / mockowanie na poziomie portu lub `respx` |

Obecny kod (`openrouter.py:48-55`, `review_response.py:57-78`) robi ręcznie to, co SDK robi w jednym wywołaniu `parse()`.

### Proponowany kształt

```python
# infrastructure/llm/openai_sdk_client.py
from openai import AsyncOpenAI

class OpenAiSdkCompletionClient(LlmCompletionPort):
    def __init__(self, *, base_url: str, api_key: str | None, model: str, timeout: float) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key or "not-needed",
            timeout=timeout,
        )

    async def complete_structured[T: BaseModel](
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_model,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise LlmParseError("Model returned no parsed structured output")
        return parsed
```

`AdrReviewService` woła `complete_structured(..., response_model=ReviewPayload)` z domeny; mapuje `ReviewPayload` → `ReviewResult`.

Factory (`factory.py`) — jedna ścieżka:

| `llm_provider` | Implementacja |
|----------------|---------------|
| `fake` | `FakeReviewer` / fake port (bez SDK) |
| `openrouter` | `AsyncOpenAI(base_url=openrouter_default, api_key=...)` |
| `openai_compatible` | `AsyncOpenAI(base_url=settings.llm_base_url, api_key=...)` |

### Zależność

Dodać `openai` do `backend/pyproject.toml` (`uv lock` z `exclude-newer = "7 days"`). `httpx` zostaje jako transitive dependency SDK — nie trzeba go usuwać z projektu.

### Ryzyka i mitigacje

1. **`json_schema` strict na OpenRouter / Ollama** — nie każdy endpoint wspiera `strict: True` tak samo jak OpenAI. Mitigacja: fallback w factory lub w kliencie — jeśli `parse()` rzuca błąd providera, retry z `response_format={"type": "json_object"}` + `ReviewPayload.model_validate_json(content)` (schema nadal z domeny, prompt z `review_instructions`).
2. **Ollama Cloud** — structured output niewspierany (research Exa); lokalny Ollama przez `/v1` często działa. Dla Cloud: schema w prompcie + `json_object` lub tool calling — bez zmiany modeli domenowych.
3. **SDK ≠ domena** — `ReviewPayload` z `Field(description=...)` zostaje w `domain/adr/`; SDK tylko transportuje schema do API.
4. **Testy** — zachować testy na poziomie portu (`LlmCompletionPort` fake) i 1–2 testy integracyjne adaptera z mockowanym HTTP SDK (lub wstrzykniętym `AsyncOpenAI` z custom transportem).

### Aktualizacja faz implementacji

| Faza | Zmiana |
|------|--------|
| **2** | Zamiast `ChatCompletionsClient` (raw httpx) → `OpenAiSdkCompletionClient` |
| **5** | Domyślnie `chat.completions.parse`; fallback `json_object` tylko gdy provider nie wspiera strict schema |

### Zaktualizowane open questions

- ~~Czy budować własny HTTP client?~~ → **Nie** — użyć OpenAI SDK w infrastructure.
- Fallback policy per `llm_provider`: `strict` vs `json_object` — ustalić w planie (np. `openrouter` = strict first; `openai_compatible` = konfigurowalne przez env `LLM_STRUCTURED_OUTPUT_MODE`).
