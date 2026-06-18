# Structured Logging (Backend) Implementation Plan

## Overview

Wprowadzamy **structlog** jako jednolity mechanizm logowania w backendzie FastAPI, zastępując rozproszone wywołania stdlib `logging`. Uzupełniamy logi w kluczowych miejscach (async event flow, LLM, commands, HTTP boundary) z hierarchicznymi nazwami zdarzeń i polami korelacji (`stored_event_id`, `adr_id`, `user_id`, `duration_ms`). Format: JSON w produkcji (`LOG_JSON=true`), czytelny console renderer lokalnie.

## Current State Analysis

- `main.py` ustawia wyłącznie `logging.basicConfig(level=logging.INFO)`.
- Stdlib logi w 4 plikach: `bootstrap.py`, `task_group_bus.py`, `dispatcher.py`, `main.py`.
- Brak `structlog` w `pyproject.toml`; brak modułu konfiguracji logów.
- `run_ai_review.py` i command handlery — zero logów; async review flow jest niewidoczny w logach.
- Brak HTTP middleware; auth przez `get_current_user_id` w `dependencies.py` bez logów.
- Test `test_dispatcher_skips_unknown_event_types` asercuje tekst wiadomości stdlib — wymaga aktualizacji po migracji.
- Sink produkcyjny: stdout → GCP Cloud Logging (`context/foundation/infrastructure.md`).

### Key Discoveries:

- Research (`context/changes/struct/research.md`) mapuje konkretne eventy i pola per plik.
- `stored_event_id` z `submit_adr_for_review` koreluje cały przepływ HTTP → command → bus → handler → LLM.
- Warstwa `domain/` pozostaje bez logów (hexagonal architecture).
- Query handlery — poza scope (decyzja planowania).

## Desired End State

Backend emituje strukturalne logi JSON na stdout w produkcji i czytelne logi w dev. Kluczowy przepływ review (`POST submit-review` → async handler → LLM) jest śledzony po `stored_event_id` / `adr_id`. Istniejące stdlib logi są zmigrowane; nowe logi pokrywają P0–P2 z research. Sekrety (`api_key`, `DATABASE_URL`, pełny markdown ADR, email) nigdy nie trafiają do logów.

### Weryfikacja:

1. `just dev-backend` — logi czytelne w terminalu (console renderer).
2. `LOG_JSON=true uv run uvicorn main:app` — każda linia to poprawny JSON z polem `event`.
3. Submit ADR for review → w logach widać łańcuch: `command.submit_adr_for_review.completed` → `dispatcher.dispatch.started` → `handler.run_ai_review.*` → `llm.review.*`.
4. `cd backend && uv run pytest` i `uv run ruff check .` — zielone.

## What We're NOT Doing

- Logowanie w `domain/` i `application/queries/`.
- Persistence debug logs (P3: `event_store`, projections, `unit_of_work`).
- OpenTelemetry / distributed tracing (structlog ma być OTel-ready, ale integracja poza scope).
- Logowanie pełnego emaila, markdown ADR, API key, raw LLM response body.
- Frontend logging.
- Metryki i error tracking (Sentry itp.).

## Implementation Approach

1. **Fundament — podział warstwowy** — `application/logging.py` eksportuje `get_logger()` (cienki wrapper na structlog); `infrastructure/logging.py` eksportuje wyłącznie `configure_logging()` wywoływane przy starcie. **`application/` nigdy nie importuje `infrastructure/`** — zależność idzie infrastructure → application.
2. **Konwencja** — hierarchiczne `event`: `warstwa.komponent.akcja` (np. `handler.run_ai_review.completed`); kontekst przez `logger.bind(...)` lub keyword args structlog.
3. **Inkrementalne fazy** — P0 async → P1 LLM/dispatcher → P2 HTTP/commands+middleware; każda faza merge-ready.
4. **Redakcja** — jawna lista zabronionych pól w Critical Implementation Details; `content_length` / `markdown_length` zamiast treści.

## Critical Implementation Details

**Redakcja i zakazane pola** — nigdy nie logować: `api_key`, `DATABASE_URL`, `jwt_secret`, pełny `email`, pełny `markdown`/`content`, raw HTTP response body z LLM. Dozwolone: `email_domain` (część po `@`), `content_length`, `title` (krótki), `has_content_change`.

**Kolejność startu** — `configure_logging()` musi wykonać się przed pierwszym logiem w `create_app()` i w `main.py` (przed importem side-effectów uvicorn). Wywołać na początku `create_app()` oraz w `main.py` przed `create_app()` gdy uruchamiany bezpośrednio.

**structlog + stdlib** — użyć integracji `structlog.stdlib` (ProcessorFormatter + `LoggerFactory`), żeby `caplog` w testach nadal działał dla logów przechodzących przez stdlib bridge.

**Granica hexagonalna** — pliki w `application/` (commands, handlers, `dispatcher.py`) importują `get_logger` z `application.logging`. Pliki w `infrastructure/` importują `configure_logging` z `infrastructure.logging` oraz `get_logger` z `application.logging`. Konfiguracja structlog (renderery, procesory, poziom) żyje wyłącznie w infrastructure; application zna tylko API `get_logger(__name__)`.

## Phase 1: Structlog Foundation

### Overview

Dodać zależność structlog, moduł konfiguracji, ustawienia env, zmigrować istniejące 4 pliki stdlib na `get_logger()`.

### Changes Required:

#### 1. Zależność

**File**: `backend/pyproject.toml`

**Intent**: Dodać `structlog` do dependencies i odświeżyć lock (`uv lock`).

**Contract**: Nowa zależność `structlog` w `[project].dependencies`.

#### 2. Ustawienia logowania

**File**: `backend/infrastructure/config.py`

**Intent**: Udostępnić przełącznik formatu i poziom logów z env.

**Contract**: Pola `log_json: bool` (`LOG_JSON`, default `false`) i `log_level: str` (`LOG_LEVEL`, default `"INFO"`). Walidator akceptujący standardowe poziomy logging.

#### 3a. Fabryka loggerów (application)

**File**: `backend/application/logging.py` (nowy)

**Intent**: Udostępnić `get_logger()` warstwie application bez importu infrastructure.

**Contract**:
- `get_logger(name: str)` — zwraca `structlog.get_logger(name)` (stdlib bridge po `configure_logging()`).
- Brak konfiguracji renderów/procesorów w tym module — tylko re-export API.

#### 3b. Konfiguracja structlog (infrastructure)

**File**: `backend/infrastructure/logging.py` (nowy)

**Intent**: Jednorazowa konfiguracja structlog przy starcie aplikacji.

**Contract**:
- `configure_logging(*, log_json: bool, log_level: str) -> None` — idempotentna konfiguracja (bezpieczna przy wielokrotnym wywołaniu w testach).
- Prod (`log_json=True`): `JSONRenderer`, jedna linia JSON na stdout (GCP Cloud Logging).
- Dev (`log_json=False`): `ConsoleRenderer` z kolorami.
- Wspólne procesory: `merge_contextvars`, `add_log_level`, `TimeStamper(fmt="iso")`, `StackInfoRenderer`, `format_exc_info`; pole `event` jako główna wiadomość (nie `message`).
- **Bez** `get_logger` — infrastructure nie jest miejscem na API używane przez application.

#### 4. Entry point

**File**: `backend/main.py`

**Intent**: Usunąć `basicConfig`; skonfigurować structlog przed utworzeniem app.

**Contract**: Import `load_settings` + `configure_logging`; wywołanie `configure_logging` przed `create_app()`.

#### 5. Migracja istniejących logów

**Files**: `backend/infrastructure/bootstrap.py`, `backend/infrastructure/messaging/task_group_bus.py`, `backend/application/runtime/dispatcher.py`

**Intent**: Zamienić `logging.getLogger` na `get_logger` z `application.logging`; przekonwertować istniejące wpisy na structured `event` + pola.

**Contract**:
- Import: `from application.logging import get_logger` (zarówno w `application/` jak i `infrastructure/`).
- `bootstrap.py`: wywołać `configure_logging(...)` na początku `create_app()`; `event="bootstrap.database_engine_created"`; LLM config → `event="bootstrap.llm_configured"` z polami `provider`, `model`, `base_url_configured`, `api_key_configured`, `timeout_seconds` (bez wartości sekretów).
- `task_group_bus.py`: `event="event_bus.drain_failed"` z `exc_info=True` zamiast plain string.
- `dispatcher.py`: `event="dispatcher.no_handler"` z `event_type`, `stored_event_id` (zachować poziom WARNING).

#### 6. Dokumentacja env

**File**: `backend/.env.example` (jeśli istnieje) lub komentarz w root `.env.example`

**Intent**: Udokumentować `LOG_JSON` i `LOG_LEVEL` dla devcontainer/deploy.

**Contract**: Komentarze z przykładowymi wartościami; bez zmiany wymaganych pól Settings.

#### 7. Test konfiguracji (opcjonalny, lekki)

**File**: `backend/tests/infrastructure/test_logging.py` (nowy)

**Intent**: Smoke test — `configure_logging` (infrastructure) + `get_logger` (application) działają razem.

**Contract**: Test wywołuje `configure_logging` z `infrastructure.logging`, potem `get_logger(__name__)` z `application.logging`; dwa warianty: `log_json=True` (parsowalny JSON z `event`) i `log_json=False` (brak wyjątku).

### Success Criteria:

#### Automated Verification:

- Lock odświeżony: `cd backend && uv lock`
- Lint: `cd backend && uv run ruff check .`
- Format: `cd backend && uv run ruff format --check .`
- Types: `cd backend && uv run ty check`
- Tests: `cd backend && uv run pytest tests/infrastructure/test_logging.py` (jeśli dodany) oraz pełny `uv run pytest`

#### Manual Verification:

- `just dev-backend` — logi startupu czytelne w terminalu
- `LOG_JSON=true` + uruchomienie serwera — stdout to JSON lines z polem `event`

**Implementation Note**: Po fazie 1 i przejściu automated verification — potwierdzenie manualne przed fazą 2.

---

## Phase 2: Async Event Flow (P0)

### Overview

Logowanie serca async processing: worker event bus, bootstrap replay/drain, handler `run_ai_review` z pełnym lifecycle (retry, idempotency, sukces/porażka).

### Changes Required:

#### 1. Event bus worker

**File**: `backend/infrastructure/messaging/task_group_bus.py`

**Intent**: Logować lifecycle workera i cykle drain z polami korelacji.

**Contract**: Eventy (poziom INFO unless noted):
- `event_bus.worker_started` — `poll_interval_seconds`
- `event_bus.worker_already_running` — DEBUG, idempotent skip
- `event_bus.dispatch_inline` — `stored_event_id`, `event_type` (w `dispatch_now`)
- `event_bus.dispatch_not_configured` — WARNING
- `event_bus.worker_stopping` / `event_bus.worker_stopped`
- `event_bus.drain_cycle` — DEBUG, `drained_count`
- `event_bus.drain_failed` — ERROR, `exc_info=True` (już częściowo; ujednolicić do structured)

#### 2. Bootstrap replay i lifespan

**File**: `backend/infrastructure/bootstrap.py`

**Intent**: Korelacja startup replay z event bus; structured shutdown.

**Contract**:
- `_replay_unprocessed_events`: `bootstrap.replay_started`, `bootstrap.replay_completed` z `total_batches` lub równoważnym licznikiem
- `_drain_unprocessed_events`: `bootstrap.drain_batch` — `loaded_count`, `event_ids` (lista UUID jako stringi)
- Per event w drain: `bootstrap.event_dispatched` — `stored_event_id`, `event_type`
- Lifespan: `bootstrap.worker_started`, `bootstrap.ready`, `bootstrap.shutdown_started`, `bootstrap.engine_disposed`

#### 3. Run AI review handler

**File**: `backend/application/handlers/run_ai_review.py`

**Intent**: Pełna widoczność async review — najwyższy priorytet diagnostyczny.

**Contract**: Eventy wg research (wszystkie ze structured polami):
- `handler.run_ai_review.started` — `stored_event_id`, `adr_id`, `user_id`
- `handler.run_ai_review.skipped` — `reason` ∈ `wrong_event_type`, `adr_not_found`, `already_reviewed`, `duplicate_failure` + odpowiednie pola (`adr_id`, `status`, `source_event_id`)
- `handler.run_ai_review.attempt` — `adr_id`, `attempt`, `max_attempts`
- `handler.run_ai_review.llm_call_started` — `adr_id`, `attempt`, `content_length` (len markdown, nie treść)
- `handler.run_ai_review.validation_failed` — `adr_id`, `attempt`, `failures` (lista stringów z validatora — OK, to metadane jakości)
- `handler.run_ai_review.llm_call_failed` — `adr_id`, `attempt`, `error` (str(exc), bez stack trace jeśli retry kontynuuje; ERROR z `exc_info` przy ostatniej próbie)
- `handler.run_ai_review.completed` — `adr_id`, `annotation_count`
- `handler.run_ai_review.failed` — `adr_id`, `last_error`, `attempts`
- `_complete_review`: `handler.run_ai_review.persistence_completed` — `completion_event_id`, `source_event_id`
- `_fail_review`: `handler.run_ai_review.failure_persisted` — `code`, `message`
- `_mark_processed`: `handler.run_ai_review.marked_processed` — `event_id`

**Uwaga**: Poprawić pętlę retry — obecnie `_attempt` nie jest używany; użyć `attempt` 1-based w logach i warunkach.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run ruff check .`
- `cd backend && uv run ty check`
- `cd backend && uv run pytest tests/application/handlers/ tests/application/runtime/ tests/infrastructure/` (istniejące testy handlerów/dispatchera bez regresji)

#### Manual Verification:

- Submit review na ADR w dev → w logach widać `handler.run_ai_review.started` i terminal state (`completed` lub `failed`)
- Restart aplikacji z nieprzetworzonym eventem → `bootstrap.replay_*` i `bootstrap.event_dispatched` w logach
- Idempotent replay (ADR już `after_review`) → `handler.run_ai_review.skipped` z `reason=already_reviewed`

**Implementation Note**: Pauza na manual confirmation przed fazą 3.

---

## Phase 3: LLM Adapters & Dispatcher (P1)

### Overview

Logowanie wywołań zewnętrznych LLM (latency, błędy HTTP) oraz rozszerzenie dispatchera o start/complete/fail z `duration_ms`.

### Changes Required:

#### 1. OpenRouter adapter

**File**: `backend/infrastructure/llm/openrouter.py`

**Intent**: Obserwowalność HTTP do OpenRouter bez wycieku sekretów.

**Contract**:
- `llm.review.request_started` — `provider="openrouter"`, `model`, `markdown_length`, `timeout_seconds`
- `llm.review.http_completed` — `status_code`, `duration_ms`
- `llm.review.http_error` — `error_type`, opcjonalnie `status_code`
- `llm.review.parsed` — `annotation_count`
- Pomiar `duration_ms` wokół `client.post` (`time.perf_counter`).

#### 2. OpenAI-compatible adapter

**File**: `backend/infrastructure/llm/openai_compatible.py`

**Intent**: Ten sam kontrakt co OpenRouter z `provider="openai_compatible"`.

**Contract**: Identyczny zestaw eventów jak OpenRouter.

#### 3. LLM factory

**File**: `backend/infrastructure/llm/factory.py`

**Intent**: Log przy budowie reviewera (bez kluczy).

**Contract**: `llm.reviewer_built` — `provider`, `model`.

#### 4. Parse validation (jeśli dotyczy)

**File**: `backend/infrastructure/llm/review_response.py`

**Intent**: DEBUG log przy parse validation failure.

**Contract**: `llm.review.parse_validation_failed` — `reason`; poziom DEBUG.

#### 5. Event dispatcher

**File**: `backend/application/runtime/dispatcher.py`

**Intent**: Pełny lifecycle dispatch z czasem wykonania.

**Contract**:
- `dispatcher.dispatch.started` — `event_type`, `stored_event_id`
- `dispatcher.dispatch.completed` — `event_type`, `stored_event_id`, `duration_ms`
- `dispatcher.dispatch.failed` — `event_type`, `stored_event_id`, `error`, `duration_ms`, `exc_info=True`
- `dispatcher.no_handler` — rozszerzyć o `stored_event_id` (z fazy 1)

#### 6. Aktualizacja testu dispatchera

**File**: `backend/tests/application/runtime/test_dispatcher.py`

**Intent**: Dostosować asercję do structured logów.

**Contract**: `test_dispatcher_skips_unknown_event_types` — asercja na `dispatcher.no_handler` (event name w JSON/stdlib record lub structlog testing helper) zamiast substring `"No handler registered"`.

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest tests/application/runtime/test_dispatcher.py`
- `cd backend && uv run pytest tests/infrastructure/llm/` (jeśli istnieją)
- `cd backend && uv run ruff check . && uv run ty check`

#### Manual Verification:

- Z `LLM_PROVIDER=fake` — `llm.reviewer_built` przy starcie; brak HTTP logów
- Z prawdziwym providerem (opcjonalnie) — `llm.review.request_started` → `http_completed` z `duration_ms`

**Implementation Note**: Pauza na manual confirmation przed fazą 4.

---

## Phase 4: HTTP Boundary & Commands (P2)

### Overview

Audit trail command handlerów, logi auth failures, route-level HTTP outcomes, middleware `http.request_completed`.

### Changes Required:

#### 1. Command handlers

**Files**:
- `backend/application/commands/submit_adr_for_review.py`
- `backend/application/commands/create_adr.py`
- `backend/application/commands/update_adr_content.py`
- `backend/application/commands/register_user.py`

**Intent**: Started / rejected / completed z polami korelacji; `submit_adr_for_review` kluczowy dla `stored_event_id`.

**Contract** (wzorzec `command.<name>.<outcome>`):
- **submit_adr_for_review**: `started` (`adr_id`, `user_id`); `rejected` (`reason`, `current_status`); `event_appended` (`adr_id`, `stored_event_id`); `completed` (`adr_id`, `stored_event_id`)
- **create_adr**: `started` (`user_id`, `title`); `rejected` (`reason=title_exists`); `completed` (`adr_id`, `user_id`, `title`)
- **update_adr_content**: `started` (`adr_id`); `rejected` (`reason`); `completed` (`adr_id`, `has_title_change`, `has_content_change`)
- **register_user**: `started` (`email_domain`); `rejected` (`reason`); `completed` (`user_id`, `email_domain`)

Domain errors (`AdrNotFound`, `DomainError`) — log `rejected` przed re-raise w handlerze lub w routerze; preferencja: **w command handlerze** przed raise, żeby audit trail był niezależny od transportu.

#### 2. Auth dependencies

**File**: `backend/infrastructure/api/dependencies.py`

**Intent**: Logować tylko odrzucenia auth (decyzja planowania).

**Contract**:
- `auth.missing_cookie` — INFO, `path` (z `request.url.path`)
- `auth.invalid_token` — INFO, `path`
- Bez logów przy udanym `get_current_user_id`.

#### 3. Auth router

**File**: `backend/infrastructure/api/routers/auth.py`

**Intent**: Logować wyniki register/login bez PII.

**Contract**:
- `route.auth.register.completed` / `route.auth.register.rejected` — `reason`, `status_code`
- `route.auth.login.completed` / `route.auth.login.rejected` — `reason=invalid_credentials`, `status_code` (bez emaila)
- Tylko na poziomie routera (nie duplikować command/query logów jeśli te same fakty).

#### 4. ADR router

**File**: `backend/infrastructure/api/routers/adr.py`

**Intent**: Jeden structured log per route invocation — sukces lub mapped HTTP error.

**Contract**: Wzorzec `route.adrs.<action>.completed|rejected` z `adr_id`, `status_code`, `reason` (dla 404/403/409/400). Priorytet: `submit_adr_for_review` (202), `create_adr`, `update_adr`, `beacon_save_adr`. Read routes (`get`, `list`, `search`, `review-status`) — opcjonalnie tylko `rejected` paths (mniej szumu).

#### 5. HTTP middleware

**File**: `backend/infrastructure/api/middleware/request_logging.py` (nowy) + rejestracja w `bootstrap.py`

**Intent**: Jeden log per HTTP request z czasem i statusem.

**Contract**:
- `http.request_completed` — `method`, `path` (szablon route jeśli dostępny, inaczej `url.path`), `status_code`, `duration_ms`
- Opcjonalnie `user_id` gdy dostępny w `request.state` (ustawić w middleware auth lub po `get_current_user_id` — jeśli zbyt skomplikowane, pominąć `user_id` w middleware i polegać na logach route)
- Pomijać `/health` i `/api/health` (DEBUG lub brak logu)
- Middleware dodane w `create_app()` **po** `CORSMiddleware` (outermost = loguje final response)

### Success Criteria:

#### Automated Verification:

- `cd backend && uv run pytest`
- `cd backend && uv run ruff check . && uv run ty check`
- `pre-commit run --all-files` (z root repo)

#### Manual Verification:

- Request bez cookie do chronionego endpointu → `auth.missing_cookie` + `http.request_completed` ze `status_code=401`
- `POST /api/adrs/{id}/submit-review` → łańcuch od `route.adrs.submit_review` przez `command.submit_adr_for_review` do handlerów z fazy 2
- `LOG_JSON=true` — pełny flow daje parsowalne JSON lines

**Implementation Note**: Ostatnia faza — manual E2E przed zamknięciem change.

---

## Testing Strategy

### Unit Tests:

- `test_logging.py` — konfiguracja structlog (faza 1)
- `test_dispatcher.py` — zaktualizowana asercja structured event (faza 3)
- Nie testować każdego log line — wystarczy smoke + krytyczne ścieżki

### Integration Tests:

- Istniejące testy replay/idempotency (`test_dispatcher.py` klasa replay) — muszą przechodzić bez zmiany zachowania
- Brak nowych testów wymuszających obecność logów w każdym teście integracyjnym (unikamy kruchych asercji na stdout)

### Manual Testing Steps:

1. Dev console: submit review → prześledź łańcuch eventów w terminalu
2. `LOG_JSON=true` + `jq` na stdout
3. Restart z pending eventem → bootstrap replay logi
4. Auth failure → tylko `auth.*` bez udanego login log

## Performance Considerations

- Logi na INFO w gorących ścieżkach (drain cycle) tylko na DEBUG; worker drain co ~50ms — unikać INFO per idle cycle.
- `event_ids` w `bootstrap.drain_batch` — max 100 (limit `load_unprocessed`); akceptowalne.
- JSON serialization na stdout — znikomy overhead vs LLM HTTP.

## Migration Notes

- Istniejące deploymenty: ustawić `LOG_JSON=true` na Cloud Run.
- Lokalny dev: domyślnie `LOG_JSON=false` (brak zmiany dla developerów).
- Brak migracji danych.

## References

- Research: `context/changes/struct/research.md`
- Infrastructure / GCP logs: `context/foundation/infrastructure.md`
- Backend architecture (no domain logs): `context/foundation/application-architecture.md`
- Istniejące logi: `backend/infrastructure/bootstrap.py`, `backend/infrastructure/messaging/task_group_bus.py`, `backend/application/runtime/dispatcher.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Structlog Foundation

#### Automated

- [x] 1.1 Lock odświeżony: `cd backend && uv lock` — f7db9a9
- [x] 1.2 Lint: `cd backend && uv run ruff check .` — f7db9a9
- [x] 1.3 Format: `cd backend && uv run ruff format --check .` — f7db9a9
- [x] 1.4 Types: `cd backend && uv run ty check` — f7db9a9
- [x] 1.5 Tests: `cd backend && uv run pytest` — f7db9a9

#### Manual

- [x] 1.6 `just dev-backend` — logi startupu czytelne w terminalu — f7db9a9
- [x] 1.7 `LOG_JSON=true` + uruchomienie serwera — stdout to JSON lines z polem `event` — f7db9a9

### Phase 2: Async Event Flow (P0)

#### Automated

- [x] 2.1 `cd backend && uv run ruff check .` — 7369b32
- [x] 2.2 `cd backend && uv run ty check` — 7369b32
- [x] 2.3 `cd backend && uv run pytest tests/application/handlers/ tests/application/runtime/ tests/infrastructure/` — 7369b32

#### Manual

- [x] 2.4 Submit review → `handler.run_ai_review.started` i terminal state w logach — 7369b32
- [x] 2.5 Restart z nieprzetworzonym eventem → `bootstrap.replay_*` w logach — 7369b32
- [x] 2.6 Idempotent replay → `handler.run_ai_review.skipped` z `reason=already_reviewed` — 7369b32

### Phase 3: LLM Adapters & Dispatcher (P1)

#### Automated

- [x] 3.1 `cd backend && uv run pytest tests/application/runtime/test_dispatcher.py` — 444ecb8
- [x] 3.2 `cd backend && uv run ruff check . && uv run ty check` — 444ecb8

#### Manual

- [x] 3.3 `LLM_PROVIDER=fake` — `llm.reviewer_built` przy starcie — 444ecb8
- [x] 3.4 (Opcjonalnie) prawdziwy provider — `llm.review.request_started` → `http_completed` — 444ecb8

### Phase 4: HTTP Boundary & Commands (P2)

#### Automated

- [x] 4.1 `cd backend && uv run pytest`
- [x] 4.2 `cd backend && uv run ruff check . && uv run ty check`
- [x] 4.3 `pre-commit run --all-files`

#### Manual

- [x] 4.4 Request bez cookie → `auth.missing_cookie` + `http.request_completed` 401
- [x] 4.5 Submit review E2E — pełny łańcuch logów
- [x] 4.6 `LOG_JSON=true` — parsowalne JSON lines dla pełnego flow
