---
date: 2026-06-18T00:00:00+00:00
researcher: Cursor Agent
git_commit: 058d6fd5cf14d679d1037b4961f732c8388c020d
branch: main
repository: adr-flow
topic: "Miejsca do ustawienia structured logów w backendzie"
tags: [research, codebase, structlog, logging, backend, task-group-bus, run-ai-review]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
---

# Research: Miejsca do ustawienia structured logów w backendzie

**Date**: 2026-06-18
**Researcher**: Cursor Agent
**Git Commit**: `058d6fd5cf14d679d1037b4961f732c8388c020d`
**Branch**: main
**Repository**: adr-flow

## Research Question

Wskazać miejsca, w których najlepiej ustawić logi dla aplikacji backendowej. Punkty startowe użytkownika: `backend/infrastructure/messaging/task_group_bus.py` oraz `backend/application/handlers/run_ai_review.py`. Zidentyfikować inne miejsca wymagające logowania.

## Summary

Backend używa dziś wyłącznie stdlib `logging` w czterech miejscach produkcyjnych (`main.py`, `bootstrap.py`, `dispatcher.py`, `task_group_bus.py`). Brak structlog, brak middleware HTTP, brak logów w command handlerach, LLM adapterach i routerach.

**Najwyższy priorytet logowania** (wg wartości diagnostycznej i ryzyka operacyjnego):

1. **`run_ai_review.py`** — retry LLM, idempotency skip, sukces/porażka review (async, trudny do debugowania bez logów)
2. **`task_group_bus.py` + `bootstrap.py`** — lifecycle workera, drain/replay eventów, korelacja `stored_event_id`
3. **`infrastructure/llm/`** — latency i błędy wywołań zewnętrznych (bez treści markdown / API key)
4. **Command handlers** — audit trail zapisów (szczególnie `submit_adr_for_review.py` jako trigger async flow)
5. **API routers + `dependencies.py`** — granica HTTP/auth, mapowanie błędów na statusy
6. **`dispatcher.py`** — rozszerzenie istniejącego warningu o start/complete/fail z `duration_ms`

**Nie logować w `domain/`** — zgodnie z hexagonal architecture. Sekrety (`api_key`, `DATABASE_URL`, pełny markdown ADR) nigdy w logach.

**Sink produkcyjny**: stdout → GCP Cloud Logging (Cloud Run), zgodnie z `context/foundation/infrastructure.md`.

## Detailed Findings

### Stan obecny — istniejące logi

| Plik | Co jest dziś |
|------|--------------|
| [`backend/main.py`](https://github.com/web-lizzard/adr-flow/blob/058d6fd5cf14d679d1037b4961f732c8388c020d/backend/main.py#L6) | `logging.basicConfig(level=logging.INFO)` |
| [`backend/infrastructure/bootstrap.py`](https://github.com/web-lizzard/adr-flow/blob/058d6fd5cf14d679d1037b4961f732c8388c020d/backend/infrastructure/bootstrap.py#L120-L128) | `logger.info` — engine + konfiguracja LLM (bez sekretów) |
| [`backend/application/runtime/dispatcher.py`](https://github.com/web-lizzard/adr-flow/blob/058d6fd5cf14d679d1037b4961f732c8388c020d/backend/application/runtime/dispatcher.py#L24-L26) | `logger.warning` — brak handlera dla typu eventu |
| [`backend/infrastructure/messaging/task_group_bus.py`](https://github.com/web-lizzard/adr-flow/blob/058d6fd5cf14d679d1037b4961f732c8388c020d/backend/infrastructure/messaging/task_group_bus.py#L65) | `logger.exception` — drain failed |

### 1. `task_group_bus.py` (wybór użytkownika)

Worker async to serce przetwarzania eventów. Dziś loguje tylko wyjątki z `drain_fn`.

| Linie | Event | Pola |
|-------|-------|------|
| 25–37 `start_worker` | `event_bus.worker_started` | `poll_interval_seconds` |
| 31–32 | `event_bus.worker_already_running` | — (idempotency skip) |
| 39–42 `dispatch_now` | `event_bus.dispatch_inline` | `stored_event_id`, `event_type` |
| 40–41 | `event_bus.dispatch_not_configured` | warning |
| 44–53 `stop_worker` | `event_bus.worker_stopping` / `stopped` | — |
| 62–68 `_run_worker` | `event_bus.drain_cycle` | `drained_count` (debug) |
| 65 | `event_bus.drain_failed` | `exc_type` (już jest exception log) |

### 2. `run_ai_review.py` (wybór użytkownika)

Najbardziej krytyczny handler — retry, idempotency, zewnętrzne LLM, persystencja wyniku.

| Linie | Event | Pola |
|-------|-------|------|
| 26 | `handler.run_ai_review.started` | `stored_event_id`, `adr_id`, `user_id` |
| 28–29 | `handler.run_ai_review.skipped` | `reason=wrong_event_type` |
| 36–38 | `handler.run_ai_review.skipped` | `reason=adr_not_found`, `adr_id` |
| 40–42 | `handler.run_ai_review.skipped` | `reason=already_reviewed`, `status` |
| 44–49 | `handler.run_ai_review.skipped` | `reason=duplicate_failure`, `source_event_id` |
| 52 | `handler.run_ai_review.attempt` | `adr_id`, `attempt`, `max_attempts` |
| 54 | `handler.run_ai_review.llm_call_started` | `adr_id`, `attempt`, `content_length` |
| 55–58 | `handler.run_ai_review.validation_failed` | `adr_id`, `attempt`, `failures` |
| 60–61 | `handler.run_ai_review.llm_call_failed` | `adr_id`, `attempt`, `error` |
| 57 | `handler.run_ai_review.completed` | `adr_id`, `annotation_count` |
| 63–67 | `handler.run_ai_review.failed` | `adr_id`, `last_error`, `attempts` |
| 81–99 `_complete_review` | `handler.run_ai_review.persistence_completed` | `completion_event_id`, `source_event_id` |
| 121–139 `_fail_review` | `handler.run_ai_review.failure_persisted` | `code`, `message` |
| 141–144 `_mark_processed` | `handler.run_ai_review.marked_processed` | `event_id` |

### 3. `bootstrap.py` — lifespan i replay

Koreluje z `task_group_bus` — startup replay nieprzetworzonych eventów.

| Linie | Event | Pola |
|-------|-------|------|
| 44–54 `_replay_unprocessed_events` | `bootstrap.replay_started` / `replay_completed` | `total_batches` |
| 57–66 `_drain_unprocessed_events` | `bootstrap.drain_batch` | `loaded_count`, `event_ids` |
| 64–65 (per event) | `bootstrap.event_dispatched` | `stored_event_id`, `event_type` |
| 130 | `bootstrap.replay_finished` | — |
| 131–134 | `bootstrap.worker_started` | `poll_interval_seconds` |
| 135 | `bootstrap.ready` | — |
| 136–137 shutdown | `bootstrap.shutdown_started` / `engine_disposed` | — |

### 4. `dispatcher.py` — rozszerzenie istniejącego

| Linie | Event | Pola |
|-------|-------|------|
| 20 | `dispatcher.dispatch.started` | `event_type`, `stored_event_id` |
| 24–26 | `dispatcher.no_handler` | *(istnieje)* — dodać structured fields |
| 28 | `dispatcher.dispatch.completed` | `duration_ms` |
| 28 (except) | `dispatcher.dispatch.failed` | `error` |

### 5. Command handlers — audit trail zapisów

#### `submit_adr_for_review.py` — **kluczowy** (trigger async review)

| Linie | Event | Pola |
|-------|-------|------|
| 33 | `command.submit_adr_for_review.started` | `adr_id`, `user_id` |
| 40–41 | `command.submit_adr_for_review.rejected` | `reason=not_found` |
| 43–44 | `command.submit_adr_for_review.rejected` | `reason=invalid_status`, `current_status` |
| 55–63 | `command.submit_adr_for_review.event_appended` | `adr_id`, `stored_event_id` |
| 64 | `command.submit_adr_for_review.completed` | `adr_id`, `stored_event_id` |

`stored_event_id` z tego commanda koreluje z logami `run_ai_review` i `task_group_bus`.

#### Pozostałe commandy (analogiczny wzorzec started/rejected/completed)

- `create_adr.py` — `adr_id`, `user_id`, `title` (bez pełnej treści)
- `update_adr_content.py` — `adr_id`, `has_title_change`, `has_content_change`
- `register_user.py` — `email_domain` (nie pełny email), `user_id`

### 6. LLM adapters — `infrastructure/llm/`

| Plik | Linie | Event | Pola |
|------|-------|-------|------|
| `openrouter.py` / `openai_compatible.py` | start `review` | `llm.review.request_started` | `provider`, `model`, `markdown_length`, `timeout_seconds` |
| | po HTTP POST | `llm.review.http_completed` | `status_code`, `duration_ms` |
| | except | `llm.review.http_error` | `error_type`, `status_code` |
| | success parse | `llm.review.parsed` | `annotation_count` |
| `factory.py` | build | `llm.reviewer_built` | `provider`, `model` |
| `review_response.py` | parse fail | `llm.review.parse_validation_failed` | `reason` (debug) |

**Nigdy**: `api_key`, pełny markdown, raw response body.

### 7. API boundary — routers i auth

Brak middleware HTTP — auth tylko przez `Depends(get_current_user_id)`.

#### `dependencies.py`

| Linie | Event | Pola |
|-------|-------|------|
| 81–83 | `auth.missing_cookie` | `path` |
| 85–87 | `auth.invalid_token` | `path` |

#### `routers/adr.py`

Jeden log per route: sukces + mapped HTTP error (404/403/409/400). Szczególnie:

- `submit_adr_for_review` (L60–78) — `status_code=202`, `adr_id`
- `create_adr`, `update_adr`, `beacon_save_adr`

#### `routers/auth.py`

- `register` / `login` — sukces i odrzucenie (`reason=invalid_credentials`, bez emaila)

**Sugestia**: middleware w `bootstrap.py` po utworzeniu app — `http.request_completed` z `method`, `path`, `status_code`, `duration_ms`, opcjonalnie `user_id`.

### 8. Persistence — niższy priorytet (debug drift)

- `event_store.py` — `load_unprocessed`, `mark_processed`, `unknown_event_type` (error)
- `adr_projection.py` — `apply_review_result`, `record_review_failure`, `mark_in_review_if_draft` (idempotency rowcount)
- `unit_of_work.py` — `integrity_error_mapped`, commit/rollback

Repozytoria read-only — logować tylko przy debugowaniu.

## Code References

- `backend/infrastructure/messaging/task_group_bus.py:55-78` — pętla workera, jedyny istniejący error log
- `backend/application/handlers/run_ai_review.py:26-67` — główna logika review z retry
- `backend/application/handlers/run_ai_review.py:36-49` — trzy ścieżki idempotency skip
- `backend/infrastructure/bootstrap.py:44-66` — replay i drain nieprzetworzonych eventów
- `backend/infrastructure/bootstrap.py:118-137` — lifespan startup/shutdown
- `backend/application/commands/submit_adr_for_review.py:54-64` — append eventu triggerującego async review
- `backend/application/runtime/dispatcher.py:20-28` — dispatch do handlerów
- `backend/infrastructure/llm/openrouter.py:35-85` — wywołanie HTTP do LLM
- `backend/infrastructure/api/dependencies.py:77-89` — brama auth
- `backend/main.py:6` — root `basicConfig` (do zastąpienia konfiguracją structlog)

## Architecture Insights

### Warstwy — gdzie logować

| Warstwa | Logować? | Uzasadnienie |
|---------|----------|--------------|
| `domain/` | **Nie** | Czysta logika biznesowa, brak zależności zewnętrznych |
| `application/commands/` | Tak | Audit trail komend, korelacja z event store |
| `application/handlers/` | Tak (wysoki priorytet) | Async side effects, retry, idempotency |
| `application/runtime/` | Tak | Dispatch loop, brak handlera |
| `infrastructure/api/` | Tak | Granica HTTP, auth, mapowanie błędów |
| `infrastructure/llm/` | Tak | Wywołania zewnętrzne, latency |
| `infrastructure/messaging/` | Tak (wysoki priorytet) | Worker lifecycle, drain failures |
| `infrastructure/bootstrap.py` | Tak | Startup replay, konfiguracja (bez sekretów) |
| `infrastructure/adapters/persistence/` | Opcjonalnie (debug) | Projection drift, integrity errors |

### Pola korelacji (używać wszędzie)

- `stored_event_id`, `adr_id`, `user_id`
- `event_type`, `command` / `handler` name
- `attempt`, `max_attempts`
- `duration_ms` (HTTP, LLM, dispatch)
- `reason` / `error_kind` dla skipów i odrzuceń

### Przepływ do skorelowania logami

```
POST /adrs/{id}/submit-review
  → command.submit_adr_for_review.completed (stored_event_id)
  → bootstrap.drain_batch / event_bus.drain_cycle
  → dispatcher.dispatch.started
  → handler.run_ai_review.started
  → llm.review.request_started → http_completed
  → handler.run_ai_review.completed
  → dispatcher.dispatch.completed
```

## Historical Context (from prior changes)

- `context/changes/struct/change.md` — stub, brak planu implementacji
- `context/foundation/roadmap.md` — observability oznaczone jako absent (przed obecnymi logami stdlib)
- `context/foundation/infrastructure.md` — stdout → GCP Cloud Logging; per-event error logging w TaskGroup
- `context/archive/2026-06-16-review-quality-checks/research.md` — observability zaplanowane na S-04; JSONL przed OpenTelemetry; logować każdy LLM call (prompt version, tokens, errors) — bez pełnej treści w produkcji
- `context/changes/persistence-scaffold/plan.md` — nigdy nie logować `DATABASE_URL`
- `context/changes/first-ai-review-annotations/plan.md` — unknown event types powinny być logowane (już częściowo w `dispatcher.py`)

## Related Research

- Poprzednia rozmowa: wybór biblioteki — **structlog** rekomendowany dla FastAPI + GCP Cloud Logging

## Open Questions

1. Czy dodać HTTP middleware od razu, czy w osobnej fazie?
2. Poziom logów dla auth (`auth.authenticated` — debug vs info)?
3. Czy logować query handlery (read paths) — prawdopodobnie nie na MVP
4. Integracja z OpenTelemetry — poza scope tego change, ale structlog powinien być OTel-ready
5. Schemat nazw eventów — `domain.action.outcome` vs flat `event_name`?

## Priorytetyzacja faz

| Faza | Pliki | Uzasadnienie |
|------|-------|--------------|
| **P0** | `run_ai_review.py`, `task_group_bus.py`, `bootstrap.py` (drain/replay) | Async flow, najtrudniejszy do debugowania |
| **P1** | `openrouter.py`, `openai_compatible.py`, `dispatcher.py` | Zewnętrzne wywołania, dispatch errors |
| **P2** | command handlers, `routers/adr.py`, `routers/auth.py`, `dependencies.py` | Audit trail, HTTP boundary |
| **P3** | `event_store.py`, projections, `unit_of_work.py` | Debug projection drift |
