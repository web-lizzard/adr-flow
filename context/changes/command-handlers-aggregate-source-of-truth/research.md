---
date: 2026-06-18T14:30:00Z
researcher: Cursor Agent
git_commit: 75fb2f2c827a2143fee72f87b2c0c06e5d4fef85
branch: main
repository: web-lizzard/adr-flow
topic: "Command handlers — source of truth for aggregate state (events vs projections)"
tags: [research, codebase, command-handlers, aggregates, event-sourcing, cqrs, domain-model]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
last_updated_note: "Added follow-up — annotation clearing drift across projection methods vs event fold"
---

# Research: Command handlers — source of truth for aggregate state (events vs projections)

**Date**: 2026-06-18T14:30:00Z
**Researcher**: Cursor Agent
**Git Commit**: `75fb2f2c827a2143fee72f87b2c0c06e5d4fef85`
**Branch**: main
**Repository**: web-lizzard/adr-flow

## Research Question

Co jest źródłem prawdy w handlerach command — agregaty domenowe powinny być tworzone ze eventów, a nie z projekcji.

## Summary

W adr-flow występują **dwa poziomy „źródła prawdy”**, które dziś **nie są spójne** z klasycznym event sourcingiem opartym o agregaty:

| Warstwa | Źródło prawdy (docelowe) | Źródło prawdy (faktyczne w kodzie) |
|---------|--------------------------|-------------------------------------|
| **Persystencja zapisów** | Tabela `events` (append-only) | ✅ Tabela `events` — każda zmiana stanu emituje event |
| **Stan używany przez command handler przed zapisem** | Replay streamu eventów → agregat domenowy | ❌ Tabele projekcji (`adrs`, `users`) via `AdrRepository` / `UserRepository` |
| **Reguły biznesowe / przejścia stanu** | Metody agregatu (`submit_for_review`, `publish`, …) | ❌ Logika inline w handlerach command, na `AdrReadModel` |

**Wniosek:** Command handlery **nie** odtwarzają agregatów z eventów. Ładują **projekcje** (`AdrReadModel`), egzekwują reguły w warstwie application, ręcznie tworzą eventy i aktualizują projekcje w tej samej transakcji. Agregaty `ADR` i `User` to **anemiczne dataclassy** bez `from_events()` / `apply()` — i jest to **świadoma decyzja F-02**, utrwalona testem `test_vocabulary_only.py`.

Event store ma tylko `load_unprocessed()` do replay **async handlerów** (`ADRSubmittedForReview`), nie do rehydracji agregatu po `aggregate_id`.

## Detailed Findings

### 1. Architektura deklaruje event store jako write-side source of truth

[application-architecture.md](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/foundation/application-architecture.md#L49-L54) opisuje flow command:

1. Router buduje command
2. **Command handler ładuje lub tworzy agregat**
3. **Agregat stosuje reguły i emituje eventy**
4. Eventy trafiają do `events`
5. Projektory aktualizują tabele `users` / `adrs`

Diagram submit ([application-architecture.md:160-165](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/foundation/application-architecture.md#L160-L165)) przechodzi przez `domain/adr/aggregate.py`.

Reguła w [.cursor/rules/backend-architecture.mdc](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/.cursor/rules/backend-architecture.mdc#L17-L28):

- Zmiany stanu **tylko** przez command handlery emitujące eventy
- `adrs.status` to projekcja eventów — nigdy nie ustawiana arbitralnie w API
- Query czytają **tylko** projekcje

### 2. EventStore — brak API rehydracji agregatu

Port [`EventStore`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/ports/event_store.py#L20-L36):

| Metoda | Cel |
|--------|-----|
| `append` | Dopisanie eventów do `events` |
| `load_unprocessed` | **Jedyna metoda load** — globalnie nieprzetworzone eventy async |
| `mark_processed` | Oznaczenie eventu po async handlerze |
| `mark_sync_projection_events_processed` | Bulk mark sync events przy starcie |

Implementacja [`load_unprocessed`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/event_store.py#L87-L96) filtruje **tylko** `ADRSubmittedForReview` ([L44-L45](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/event_store.py#L44-L45)). Brak filtrowania po `aggregate_id`, brak `load_stream`.

Użycie: startup replay w [`bootstrap.py`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/bootstrap.py#L46-L68) — ponowne uruchomienie **handlerów**, nie odtworzenie agregatu.

Repo-wide search: **zero** wystąpień `from_events`, `load_stream`, `rehydrate`, `apply` (event fold) w `backend/`.

### 3. Agregaty domenowe — anemiczne dataclassy

[`ADR`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/domain/adr/aggregate.py#L14-L25) i [`User`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/domain/user/aggregate.py#L7-L12) — frozen dataclassy, same pola, **bez metod**.

Test [`test_vocabulary_only.py`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/tests/domain/test_vocabulary_only.py) **wymusza** brak metod lifecycle (`submit`, `publish`, `apply`, …) i brak funkcji w modułach aggregate — komentarz: *"Aggregates remain data containers without lifecycle behavior in F-02"*.

Testy domenowe ([`test_adr.py`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/tests/domain/test_adr.py)) sprawdzają konstrukcję typów i słownik eventów, **nie** przejścia stanu na agregacie.

### 4. Command handlery — projekcja jako operational source of truth

Wszystkie 4 command handlery + async handler `RunAiReviewHandler` ładują stan z repozytoriów czytających tabele projekcji:

#### `AdrRepository` → tabela `adrs`

Port definiuje [`AdrReadModel`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/ports/adr_repository.py#L10-L22) (płaski read model, nie agregat).

Adapter [`SqlAdrRepository`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/repositories/adr_repository.py#L19-L33) robi `SELECT` na ORM `Adr`.

#### Per-handler

| Handler | Pre-read | Reguły biznesowe | Budowa `ADR` dla projekcji |
|---------|----------|------------------|----------------------------|
| [`create_adr`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/create_adr.py) | `find_by_title_for_owner` (L45-48) | Unikalność tytułu w handlerze | Ręczna konstrukcja `ADR` → `insert` (L81-92) |
| [`update_adr_content`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/update_adr_content.py) | `find_by_id_for_owner` (L35-38) | Blokada edycji w `in_review` na `existing.status` (L47-53) | Ręczna konstrukcja z pól `existing` → `update_content` (L98-109) |
| [`submit_adr_for_review`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/submit_adr_for_review.py) | `find_by_id_for_owner` (L46-49) | Tylko `draft` na `existing.status` (L58-65) | **Brak** `ADR` — tylko `mark_in_review(adr_id)` (L81-84) |
| [`register_user`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/register_user.py) | `UserRepository.find_by_email` (L53) | Email zajęty w handlerze | **Brak** `User` — `user_projection.insert(...)` (L83-88) |
| [`run_ai_review`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/handlers/run_ai_review.py) | `find_by_id_for_owner` (L48) | Idempotencja na `adr.status`, `review_error` (L58-79) | **Brak** `ADR` — `apply_review_result` / `record_review_failure` |

Wzorzec zapisu (create/update):

```
AdrRepository (projekcja) → reguły w handlerze → event_store.append → adr_projection.update
```

Event store jest **logiem zapisu**, nie **źródłem odczytu** dla command handlerów.

### 5. Ryzyko niespójności projection-first

Gdy handler czyta projekcję zamiast replay eventów:

- **Projekcja może rozjechać się z event stream** (bug w projectorze, partial failure) — handler podejmie decyzję na podstawie nieaktualnego stanu.
- **Reguły rozproszone** między handlery zamiast jednego miejsca na agregacie — trudniejsze testowanie invariantów (test-plan.md wspomina unit testy agregatu dla illegal transitions).
- **Duplikacja modeli**: `AdrReadModel` (string status) vs `ADR` (enum `AdrStatus`) vs event payload — konwersje ręczne w handlerach.

Obecnie spójność opiera się na **synchronicznej aktualizacji projekcji w tej samej transakcji UoW** co append eventu ([event_store.py L35-36](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/event_store.py#L35-L36): sync projection events nie idą przez async dispatch).

## Code References

- `backend/application/ports/event_store.py:20-36` — brak `load_stream` / `load_for_aggregate`
- `backend/infrastructure/adapters/persistence/event_store.py:87-96` — `load_unprocessed` tylko dla async dispatch
- `backend/domain/adr/aggregate.py:14-25` — anemiczny `ADR`
- `backend/application/ports/adr_repository.py:10-28` — `AdrReadModel`, nie agregat
- `backend/infrastructure/adapters/persistence/repositories/adr_repository.py:19-33` — SELECT z `adrs`
- `backend/application/commands/update_adr_content.py:35-53` — reguły na projekcji
- `backend/application/commands/submit_adr_for_review.py:46-84` — status z projekcji, event budowany w handlerze
- `backend/tests/domain/test_vocabulary_only.py:1-60` — test wymuszający brak behavior na agregatach

## Architecture Insights

### Co jest „event sourcing lite” w tym repo

- ✅ Append-only `events` jako audit log / write log
- ✅ Projekcje `users` / `adrs` jako read models
- ✅ Synchroniczna projekcja w command path (create, update, register)
- ✅ Async replay **handlerów** (AI review) przy starcie
- ❌ Rehydracja agregatu ze streamu eventów
- ❌ Rich aggregate z metodami emitującymi eventy
- ❌ Single source of truth dla **decyzji biznesowych** w command path — to dziś projekcja

### Doc vs kod

| Aspekt | Dokumentacja | Kod |
|--------|--------------|-----|
| Load aggregate | Event replay / aggregate load | Projection via repository |
| Business rules | Na agregacie | W command handlerze |
| Emit events | Agregat | Handler bezpośrednio tworzy Pydantic event |

To nie jest przypadkowy drift — F-02 **celowo** zostawił agregaty bez lifecycle ([persistence-scaffold/plan.md](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/persistence-scaffold/plan.md): *"intentionally avoid lifecycle methods and invariants until slices S-01 and S-02 introduce actual behavior"*). Slice’y S-01/S-02/S-04 dodały **zachowanie w handlerach**, nie na agregatach.

## Historical Context (from prior changes)

- [`context/changes/persistence-scaffold/research.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/persistence-scaffold/research.md) — dwa agregaty, event store + projekcje; invarianty opisane koncepcyjnie, implementacja odroczona
- [`context/changes/persistence-scaffold/plan.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/persistence-scaffold/plan.md) — domain „thin value objects, aggregates, events only”
- [`context/archive/2026-06-16-draft-authoring-persistence/plan.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/archive/2026-06-16-draft-authoring-persistence/plan.md) — `RegisterUserCommandHandler` jako wzorzec UoW + event + projection
- [`context/foundation/test-plan.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/foundation/test-plan.md) — ryzyko: event append OK, projection fail → stale read model; rekomendacja unit testów **agregatu** dla illegal transitions (jeszcze nie zaimplementowane)

## Related Research

- [`context/changes/publish-after-review/research.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/publish-after-review/research.md) — publish command ma naśladować `submit_adr_for_review` (projection-first pattern)
- [`context/changes/persistence-scaffold/research.md`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/persistence-scaffold/research.md) — model domenowy i granice agregatów

## Open Questions

1. **Czy team chce ewolucji do pełnego event-sourced aggregate load** (`EventStore.load_stream(aggregate_id)` + `ADR.from_events`) — wymaga nowego portu, refaktoru handlerów i usunięcia/zmiany `test_vocabulary_only.py`?
2. **Alternatywa pragmatyczna:** zostawić projection-first dla MVP, ale przenieść reguły przejść do modułu domenowego (pure functions na stanie agregatu, bez replay) — mniejszy koszt, lepsze testy invariantów?
3. **Kiedy projection-first staje się problemem?** Przy re-build projekcji z eventów, multi-writer, lub gdy publish/delete dodadzą kolejne reguły statusu rozproszone w handlerach (S-05, S-06)?

## Follow-up Research 2026-06-18 — dryf semantyki annotacji między projectorami

### Obserwacja użytkownika

Projection-first model wymusza **osobną decyzję per metoda projektora** co się dzieje z `review_annotations`, `reviewed_at`, `review_error`. Te decyzje są dziś **niespójne między transitionami** — publish celowo zostawia annotacje, submit je czyści, a każdy nowy feature (np. ponowny review) wymaga kolejnego ad-hoc UPDATE. W event streamie problem nie istnieje: fakty są append-only, a semantyka należy do **foldu eventów na agregacie**.

### Macierz zachowań projektora (stan obecny)

| Operacja | Metoda projektora | `status` | `review_annotations` | `reviewed_at` | `review_error` |
|----------|-------------------|----------|----------------------|---------------|----------------|
| Submit for review | `mark_in_review` | → `in_review` | **NULL** | **NULL** | **NULL** |
| Submit (optimistic) | `mark_in_review_if_draft` | → `in_review` | **NULL** | **NULL** | **NULL** |
| AI review OK | `apply_review_result` | → `after_review` | **ustaw** | **ustaw** | **NULL** |
| AI review fail | `record_review_failure` | bez zmian | bez zmian | bez zmian | **ustaw** |
| Edit content | `update_content` | bez zmian | **bez zmian** (SQL) | bez zmian | bez zmian |
| Publish | `mark_proposed` | → `proposed` | **bez zmian** | bez zmian | bez zmian |

Źródła:

- Czyszczenie przy submit: [`adr_projection.py:36-46`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/projections/adr_projection.py#L36-L46)
- Publish tylko status: [`adr_projection.py:49-57`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/projections/adr_projection.py#L49-L57)
- Test świadomie assertuje zachowanie publish: [`test_adr_projection_review.py:109-123`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/tests/infrastructure/adapters/persistence/test_adr_projection_review.py#L109-L123)

Plan S-05 **jawnie** wymaga tej asymetrii: *„Unlike `mark_in_review`, publish preserves annotations”* ([`publish-after-review/plan.md:69-70`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/context/changes/publish-after-review/plan.md#L69-L70)). To poprawne productowo, ale **semantyka żyje w SQL UPDATE-ach**, nie w jednym miejscu domenowym.

### Dodatkowy dryf: handler vs projektor

`UpdateAdrContentCommandHandler` buduje `ADR` z `review_result=None` ([`update_adr_content.py:104`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/update_adr_content.py#L104)), mimo że `update_content` w SQL **nie dotyka** pól review ([`adr_projection.py:25-34`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/infrastructure/adapters/persistence/projections/adr_projection.py#L25-L34)). DB zachowuje annotacje, ale obiekt domenowy w handlerze sugeruje co innego — kolejny sygnał, że agregat nie jest źródłem prawdy nawet lokalnie w command path.

### Co się stanie przy re-review (post-MVP, parked w roadmap)

Dziś invariant: submit tylko z `draft`, brak powrotu do `in_review` ([`submit_adr_for_review.py:58-65`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/commands/submit_adr_for_review.py#L58-L65)). Ponowny review wymagałby co najmniej:

1. Nowego eventu lub rozszerzenia `ADRSubmittedForReview` (np. z `after_review` / `proposed`)
2. Decyzji: czy czyścić stare annotacje przy drugim submit? (submit dziś czyści, publish nie)
3. Kolejnej metody projektora lub zmiany `mark_in_review` z warunkami statusu
4. Idempotencji w `RunAiReviewHandler` — dziś skip gdy `after_review` ([`run_ai_review.py:58-66`](https://github.com/web-lizzard/adr-flow/blob/75fb2f2c827a2143fee72f87b2c0c06e5d4fef85/backend/application/handlers/run_ai_review.py#L58-L66)) — trzeba przepisać

Każdy krok to **kolejna gałąź w projectorze**, łatwa do pominięcia w jednym z pięciu UPDATE-ów.

### Jak wyglądałoby to na event fold

Eventy już niosą właściwe fakty bez sprzeczności:

| Event | Payload review | Semantyka foldu (propozycja) |
|-------|----------------|------------------------------|
| `ADRSubmittedForReview` | `content` (snapshot do review) | `status=in_review`, wyczyść bieżący wynik review (nowy cykl) |
| `AIReviewCompleted` | `review_result` | `status=after_review`, ustaw annotacje |
| `AIReviewFailed` | metadata błędu | ustaw `review_error`, status bez zmian |
| `ADRContentUpdated` | — | aktualizuj title/content, **nie ruszaj** review state |
| `ADRPublished` | — | `status=proposed`, **nie ruszaj** review state |

Przy re-review: kolejny `ADRSubmittedForReview` + `AIReviewCompleted` **append-only** — stary review zostaje w historii, agregat bierze latest fold. Projektory stają się **materializacją** jednej funkcji `ADR.apply(event)`, nie pięcioma niezależnymi UPDATE-ami z różnymi konwencjami.

### Wniosek follow-up

Obserwacja użytkownika potwierdza, że projection-first **skaluje się źle** wraz z liczbą transitionów i wariantów review. Dryf annotacji publish vs submit nie jest bugiem — to **architekturalny koszt** rozproszonej semantyki. Event stream + fold na agregacie eliminuje klasę problemów „które kolumny NULL-ować w którym handlerze”, bo reguła jest jedna: **event → apply → stan**.

Rekomendacja na najbliższy krok (bez pełnego ES): wydzielić **pure fold** `apply_adr_event(state, event) -> state` w `domain/adr/` i używać go zarówno do rehydracji (gdy dodamy `load_stream`), jak i do synchronizacji projektorów — jeden test invariantów zamiast macierzy SQL per metoda.
