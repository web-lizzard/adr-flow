---
date: 2026-06-18T00:00:00+00:00
researcher: Cursor Agent
git_commit: 090e33db8441655c5eef4c5d9d858d467dffdd86
branch: main
repository: adr-flow
topic: "Przykład ADR który powinien przejść walidację (fixture do testów)"
tags: [research, codebase, adr, validation, f-01, fixtures]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
---

# Research: Przykład ADR który powinien przejść walidację (fixture do testów)

**Date**: 2026-06-18
**Researcher**: Cursor Agent
**Git Commit**: 090e33db8441655c5eef4c5d9d858d467dffdd86
**Branch**: main
**Repository**: adr-flow

## Research Question

Daj mi przykład ADR który powinien przejść walidację — potrzebne do testu; dodaj do `context/foundation/`.

## Summary

W repozytorium istnieje już kanoniczny fixture `backend/tests/review_quality/fixtures/complete.md` — ADR o wyborze bazy danych z pięcioma wymaganymi sekcjami i merytoryczną treścią. `find_missing_or_empty_sections()` zwraca dla niego pusty zbiór, więc przechodzi walidację luk sekcji (F-01).

„Walidacja” w produkcie ma dwa poziomy: (1) parser sekcji na markdownzie użytkownika, (2) `validate_review_result()` na outputcie LLM po submit-review. Save/submit **nie blokuje** niekompletnych ADR-ów — brakujące sekcje wychwytuje dopiero AI review.

Dodano dokument referencyjny: `context/foundation/valid-adr-example.md` (treść ADR, reguły, komendy weryfikacji).

## Detailed Findings

### Kanoniczny fixture `complete.md`

Treść (identyczna w teście `test_complete_adr_returns_empty_set`):

```markdown
## Context

We need to choose a database for the project.

## Options

1. PostgreSQL
2. MongoDB

## Decision

We will use PostgreSQL.

## Status

Accepted

## Consequences

Positive: ACID compliance. Negative: operational overhead.
```

Źródła: `backend/tests/review_quality/fixtures/complete.md`, `backend/tests/domain/adr/test_required_sections.py:10-31`.

### Reguły parsera sekcji

`backend/domain/adr/required_sections.py`:

- Wymagane nagłówki (dokładnie, case-sensitive): `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences` (`6:12`).
- Sekcja „brakująca” gdy: brak nagłówka, puste body, lub body to placeholder `tbd`/`todo`/`n/a` (`78:89`).
- `## Alternatives` nie zastępuje `## Options`; `## context` (małe c) nie pasuje (`test_required_sections.py:93-100`).
- Dodatkowe sekcje (np. `## References` w `extra_sections.md`) nie psują wyniku.

### Runtime gate na output review

`backend/application/review_quality.py:23-31`:

- Porównuje `find_missing_or_empty_sections(markdown)` z adnotacjami `missing_section` w `ReviewResult`.
- Sprawdza actionability pól wg rodzaju adnotacji (`103-124`).
- Handler `run_ai_review.py` retryuje raz z `validation_feedback`; po wyczerpaniu prób → `AIReviewFailed` z `code="validation_failed"`.

Dla kompletnego ADR poprawny wynik review: **zero** adnotacji `missing_section`. Adnotacje `inconsistency`/`conciseness` mogą się pojawić (np. `FakeReviewer`) i nadal przejść gate, o ile spełniają wymagane pola.

### Brak walidacji markdown przy zapisie

- `AdrContent` — dowolny string (`value_objects.py:42-48`).
- `SubmitAdrForReviewCommandHandler` — nie wywołuje parsera sekcji przed enqueue (`submit_adr_for_review.py:67-72`).
- Frontend — walidacja tylko tytułu przy tworzeniu; brak reguł sekcji w edytorze.

## Code References

- `backend/tests/review_quality/fixtures/complete.md` — golden input, wszystkie sekcje OK
- `backend/domain/adr/required_sections.py:6-89` — parser i `find_missing_or_empty_sections`
- `backend/domain/adr/template.py:3-5` — starter (wszystkie sekcje puste → fail)
- `backend/application/review_quality.py:23-124` — runtime validator wyniku review
- `backend/infrastructure/llm/fake_reviewer.py:14-50` — deterministyczny reviewer do testów lokalnych
- `context/foundation/valid-adr-example.md` — nowy dokument referencyjny dla testów

## Architecture Insights

- Reguły sekcji są w domenie (`domain/adr/`), współdzielone przez prompt LLM (`review_instructions.py`), fake reviewery i runtime gate.
- Fixture-driven harness w `backend/tests/review_quality/` (F-01) definiuje kontrakt jakości przed pokazaniem adnotacji użytkownikowi.
- `context/foundation/` służy dokumentom żyjącym ponad zmianami; fixture testowy pozostaje w `backend/tests/`, a foundation doc go opisuje i synchronizuje semantycznie.

## Historical Context (from prior changes)

- `context/archive/2026-06-16-review-quality-checks/plan.md` — zdefiniował zestaw golden fixtures w tym `complete.md` i reguły placeholderów/nagłówków.
- `context/archive/2026-06-17-first-ai-review-annotations/plan.md` — podłączył `validate_review_result` do workera AI review.
- `context/changes/llm-refactor/plan.md` — wymaga, by review na complete fixture przechodził bez pętli retry walidacji.

## Related Research

- `context/changes/llm-refactor/research.md` — mapowanie reguł domeny na prompt LLM
- `context/archive/2026-06-16-review-quality-checks/research.md` — pierwotny research F-01 i fixture needs

## Open Questions

- Czy synchronizować `complete.md` z foundation doc automatycznie (np. test importujący ten sam plik) — obecnie ręczna zgodność semantyczna.
- Czy dodać drugi przykład z `## References` (`extra_sections.md`) jako wariant „valid + opcjonalne sekcje” — opcjonalne dla testerów.
