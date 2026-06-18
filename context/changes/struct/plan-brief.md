# Structured Logging (Backend) — Plan Brief

> Full plan: `context/changes/struct/plan.md`
> Research: `context/changes/struct/research.md`

## What & Why

Backend ADR Flow dziś ma rozproszone stdlib logi w 4 plikach i brak widoczności async flow (submit review → event bus → AI handler → LLM). Wprowadzamy **structlog** z JSON na produkcji (GCP Cloud Logging) i uzupełniamy logowanie w kluczowych miejscach, żeby dało się skorelować request HTTP z przetwarzaniem eventów po `stored_event_id`.

## Starting Point

`logging.basicConfig` w `main.py`; logi tylko w `bootstrap.py`, `task_group_bus.py`, `dispatcher.py`. `run_ai_review.py` i command handlery są ciche. Brak structlog w zależnościach. Research mapuje priorytety P0–P2 i konkretne nazwy eventów.

## Desired End State

Jeden mechanizm logowania: `application/logging.py` (`get_logger`) + `infrastructure/logging.py` (`configure_logging` przy starcie). Application nie importuje infrastructure. Przepływ review widoczny end-to-end w logach. Hierarchiczne nazwy (`handler.run_ai_review.completed`). Bez sekretów i pełnej treści ADR. Query handlery i persistence debug poza scope.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|----------|--------|------------------|--------|
| Biblioteka | structlog | JSON + GCP; stdlib bridge dla testów | Research |
| Format wyjścia | JSON prod / console dev | Czytelność lokalnie, queryable w GCP | Plan |
| Konwencja nazw | Hierarchiczne `warstwa.komponent.akcja` | Filtrowanie po prefiksie w Cloud Logging | Plan |
| Zakres faz | P0–P2 (bez persistence P3) | Pełny audit bez szumu debug SQL | Plan |
| HTTP middleware | Faza 4 z routerami | Pełny trace HTTP→async w jednym change | Plan |
| Auth logging | Tylko błędy (INFO) | Mniej szumu; wystarczy do debug 401 | Plan |
| Query handlery | Bez logów | Reads częste i tanie | Plan |
| Logger pattern | `get_logger()` w `application/logging.py`; `configure_logging()` w infrastructure | Hexagonal: application nie importuje infrastructure | Plan |

## Scope

**In scope:** structlog setup, migracja 4 plików, P0 async (`run_ai_review`, event bus, bootstrap), P1 LLM + dispatcher, P2 commands + routers + auth + HTTP middleware, testy smoke/dispatcher.

**Out of scope:** domain logs, query logs, persistence P3, OpenTelemetry, frontend, metryki/Sentry.

## Architecture / Approach

```
bootstrap: configure_logging()  [infrastructure/logging.py]
application/infrastructure: get_logger(__name__)  [application/logging.py]
  → HTTP middleware (http.request_completed)
  → router / command (command.*.completed, stored_event_id)
  → event bus (event_bus.drain_cycle)
  → dispatcher (dispatcher.dispatch.*)
  → run_ai_review (handler.run_ai_review.*)
  → LLM adapter (llm.review.*)
```

Pola korelacji: `stored_event_id`, `adr_id`, `user_id`, `duration_ms`, `reason`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|-------|------------------|----------|
| 1. Structlog Foundation | Dep, `logging.py`, Settings, migracja 4 plików | Kolejność init vs pierwszy log |
| 2. Async Event Flow (P0) | `run_ai_review`, event bus, bootstrap replay | Dużo eventów — trzymać redakcję markdown |
| 3. LLM & Dispatcher (P1) | HTTP latency LLM, dispatch `duration_ms` | Test dispatchera wymaga aktualizacji |
| 4. HTTP & Commands (P2) | Commands audit, auth, middleware | Duplikacja logów router vs command |

**Prerequisites:** Brak — change jest samodzielny na obecnym backendzie.
**Estimated effort:** ~2–3 sesje implementacji w 4 fazach.

## Open Risks & Assumptions

- `caplog` działa przez structlog stdlib bridge — wymaga weryfikacji w fazie 1/3.
- Cloud Run deploy musi ustawić `LOG_JSON=true` (poza tym planem — notatka deploy).
- Router vs command logging może dublować wpisy — trzymać command jako source of truth dla audit, router dla HTTP status.

## Success Criteria (Summary)

- Submit review → pełny łańcuch logów po `stored_event_id` w dev i przy `LOG_JSON=true`.
- `uv run pytest`, ruff, ty — zielone po każdej fazie.
- Zero wycieków `api_key`, email, pełnego markdown w logach.
