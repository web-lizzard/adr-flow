---
date: 2026-06-18T00:00:00+00:00
researcher: Cursor Agent
git_commit: 897f5c910c2192867769a0f06caee0cdf20c5a94
branch: main
repository: adr-flow
topic: "md-editor-v3 fit for ADR Flow and toolbar customization (remove image upload etc.)"
tags: [research, frontend, markdown-editor, md-editor-v3, adr-markdown-editor, toolbar]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
---

# Research: md-editor-v3 fit for ADR Flow and toolbar customization

**Date**: 2026-06-18
**Researcher**: Cursor Agent
**Git Commit**: `897f5c910c2192867769a0f06caee0cdf20c5a94`
**Branch**: `main`
**Repository**: [adr-flow](https://github.com/web-lizzard/adr-flow)

## Research Question

Czy **md-editor-v3** (opcja 1 z wcześniejszej analizy) pasuje do projektu ADR Flow (Nuxt 4 / Vue 3), w szczególności z możliwością **customizacji toolbara** — głównie usuwania opcji takich jak dodawanie obrazka?

## Summary

**Tak — md-editor-v3 dobrze pasuje do ADR Flow** jako zamiana obecnego `AdrMarkdownEditor` opartego na `vue-codemirror6`. Biblioteka jest natywna dla Vue 3, przechowuje treść jako **markdown string** (bez zmiany kontraktu API/backendu), ma wbudowany toolbar z Jira-podobnym UX i oferuje **pełną kontrolę nad przyciskami** przez whitelist (`toolbars`), blacklist (`toolbarsExclude`) oraz `noUploadImg`.

Rekomendowany zestaw dla ADR: bold, italic, strike, nagłówki, cytat, listy, inline code, fenced code block, link, separator, ewentualnie preview — **bez** `image`, `mermaid`, `katex`, `save`, `github`. Obrazki wyłączyć trzema warstwami: wykluczyć `'image'` z toolbara, ustawić `no-upload-img`, nie implementować `onUploadImg`.

Integracja wymaga niewielkiej migracji komponentu i testów; kontrakt `v-model` + `@blur` + `readonly` pozostaje kompatybilny. Główne ryzyka: własny CSS biblioteki (dopasowanie do shadcn/Tailwind), większy bundle niż sam CodeMirror, oraz `onBlur` odpalający się przy kliknięciu w toolbar (wymaga dirty-check, który już macie).

## Detailed Findings

### Obecna implementacja edytora

`AdrMarkdownEditor.client.vue` opakowuje `vue-codemirror6` z `@codemirror/lang-markdown`. Brak toolbara — użytkownik pisze surowy markdown z monospace fontem.

- Props: `modelValue: string`, `readonly?: boolean` (default `false`)
- Emity: `update:modelValue`, `blur` (syntetyczny — z `@focus=false` CodeMirror, nie natywny DOM blur)
- Gdy `readonly`, komponent nie emituje ani `update:modelValue`, ani `blur`

Jedyny produkcyjny consumer: `frontend/app/pages/workspace/adr/[id].vue` — owinięty w `<ClientOnly>` z skeleton fallback.

### Persistence i save-on-blur

Łańcuch zapisu:

1. `@update:model-value` → `onContentInput` → `adr.updateContent(value)` (ustawia `isDirty`)
2. `@blur` → `onEditorBlur` → `saveOnBlur()` z `useAdrPersistence`
3. `saveOnBlur` zapisuje tylko gdy `isReviewEditable && store.isDirty`

md-editor-v3 oferuje `@on-blur` (natywny `FocusEvent`) i `v-model` — wzorzec save-on-blur da się odtworzyć 1:1 z istniejącym dirty-checkiem. **Uwaga:** blur może się odpalić przy kliknięciu przycisku toolbara; `isDirty` guard to łagodzi.

### Brak preview w MVP

Frontend nie renderuje markdownu ADR nigdzie indziej (brak `marked`/`markdown-it` w zależnościach). `AdrCard` pokazuje tylko metadane. md-editor-v3 opcjonalnie dodaje preview w samym edytorze — można go wyłączyć z toolbara (`preview`, `previewOnly`, `htmlPreview`).

### md-editor-v3 — toolbar customization

Biblioteka v6.4.1 (MIT, aktywna społeczność ~2400★) udostępnia trzy mechanizmy:

| Mechanizm | Prop / API | Zastosowanie |
|-----------|------------|--------------|
| Whitelist | `:toolbars="ToolbarNames[]"` | Jawna lista i kolejność przycisków |
| Blacklist | `:toolbars-exclude="['image', ...]"` | Domyślny toolbar minus wybrane |
| Custom buttons | `#defToolbars` + indeksy numeryczne | Własne akcje (np. szablon sekcji ADR) |

Dostępne klucze toolbara m.in.: `bold`, `italic`, `strikeThrough`, `title`, `quote`, `unorderedList`, `orderedList`, `task`, `codeRow`, `code`, `link`, `image`, `table`, `mermaid`, `katex`, `preview`, `fullscreen`, `-` (separator), `=` (podział lewo/prawo).

Helper `allToolbar` pozwala filtrować domyślną listę:

```ts
import { allToolbar } from 'md-editor-v3'
const toolbars = allToolbar.filter((t) => t !== 'image' && t !== 'mermaid')
```

### Wyłączenie uploadu obrazków

- **`no-upload-img`** — ukrywa wbudowany UI uploadu (paste/clip modal). To oficjalny sposób; samo pominięcie `onUploadImg` **nie** wystarcza ([issue #776](https://github.com/imzbf/md-editor-v3/issues/776)).
- **`toolbars-exclude="['image']"`** lub brak `'image'` w whitelist — usuwa przycisk z paska.
- Razem: brak możliwości wstawienia obrazka przez UI.

### Tryb readonly

- `readOnly` na `MdEditor` — treść widoczna, bez edycji (jak obecny `readonly` prop).
- Alternatywa dla widoku tylko-do-odczytu: `MdPreview` (lżejszy, bez toolbara) — na razie niepotrzebny, bo ten sam komponent obsługuje `in_review`.

### Vue 3 / Nuxt 4 kompatybilność

- Peer: `vue ^3.5.3` — projekt ma `vue ^3.5.34` ✅
- Oficjalny [przykład Nuxt](https://github.com/imzbf/md-editor-v3/tree/develop/example/nuxt) bez `ClientOnly`, ale zalecane zachowanie obecnego `<ClientOnly>` + `.client.vue` (CodeMirror jest DOM-heavy).
- Stabilne `id` na edytorze zalecane przy SSR.
- `minimumReleaseAge: 10080` (7 dni) w `pnpm-workspace.yaml` — v6.4.1 (2026-03-21) spełnia politykę.

### Bundle i zależności

- Pakiet ~604 KB unpacked; runtime oparty na **CodeMirror 6** (jak obecny stack) + markdown-it + lucide-vue-next.
- Obecny `basicSetup` CodeMirror szacowany w planie na ~150 KB gzipped; md-editor-v3 będzie **większy** (toolbar, style ~69 KB CSS, markdown-it), ale zastępuje ręczną implementację toolbara.
- Opcjonalne ciężkie featury (`mermaid`, `katex`, `prettier`) — wykluczyć z toolbara; nie ładować rozszerzeń.

### Dopasowanie do konwencji projektu

| Wymaganie projektu | md-editor-v3 |
|--------------------|--------------|
| Markdown jako storage | ✅ `v-model` string |
| Save-on-blur | ✅ `@on-blur` + dirty-check |
| Readonly (`in_review`) | ✅ `readOnly` prop |
| Client-only | ✅ + istniejący `ClientOnly` |
| Brak WYSIWYG w MVP (historycznie) | ⚠️ Toolbar ≠ WYSIWYG; nadal edycja markdown ze składnią widoczną (chyba że włączysz preview) |
| shadcn/Tailwind UI | ⚠️ Własny CSS — wymaga theme override lub scoped overrides |
| Testy Vitest | Wymaga aktualizacji stubów w `adr-markdown-editor.test.ts` i `adr-editor-page.test.ts` |

### Proponowany toolbar dla ADR

```ts
const adrToolbars: ToolbarNames[] = [
  'bold',
  'italic',
  'strikeThrough',
  '-',
  'title',
  'quote',
  'unorderedList',
  'orderedList',
  '-',
  'codeRow',  // inline `
  'code',     // fenced ```
  'link',
  '=',
  'revoke',
  'next',
]
```

Wykluczone: `image`, `table`, `mermaid`, `katex`, `save`, `prettier`, `preview`, `fullscreen`, `github`, `catalog`, `task` (opcjonalnie zostaw task lists dla checklist ADR).

## Code References

- `frontend/app/components/adr/AdrMarkdownEditor.client.vue:5-18` — obecny kontrakt props/emits
- `frontend/app/components/adr/AdrMarkdownEditor.client.vue:22-32` — logika readonly i syntetyczny blur
- `frontend/app/pages/workspace/adr/[id].vue:199-209` — jedyny consumer + `ClientOnly`
- `frontend/app/pages/workspace/adr/[id].vue:71-80` — `onEditorBlur` → save
- `frontend/app/pages/workspace/adr/[id].vue:91-97` — `onContentInput` → `updateContent`
- `frontend/app/composables/useAdrPersistence.ts:18-23` — `saveOnBlur` dirty guard
- `frontend/tests/adr-markdown-editor.test.ts` — testy kontraktu komponentu
- `frontend/tests/adr-editor-page.test.ts:76-84` — stub edytora na stronie
- `frontend/package.json:17-40` — obecne zależności CodeMirror
- `frontend/pnpm-workspace.yaml:2-3` — polityka `minimumReleaseAge`

## Architecture Insights

1. **Kontrakt komponentu może pozostać stabilny** — `AdrMarkdownEditor` nadal eksportuje `modelValue`, `readonly`, `update:modelValue`, `blur`; wewnętrznie zamiana implementacji na `MdEditor`.
2. **Backend bez zmian** — ADR `content` to markdown string; AI review i walidacja sekcji nie zależą od edytora UI.
3. **Toolbar to uzupełnienie MVP, nie WYSIWYG** — historyczna decyzja wykluczała rich WYSIWYG i split preview; md-editor-v3 z wyłączonym preview nadal edytuje markdown source z pomocniczym paskiem — zgodne z duchem „szybki MVP, nie kolejny Notion”.
4. **Annotation panel pozostaje osobno** — S-04 świadomie odrzucił inline CodeMirror overlays; md-editor-v3 nie koliduje z `AdrReviewAnnotations.vue`.

## Historical Context (from prior changes)

- `context/archive/2026-06-16-draft-authoring-persistence/research.md` — MVP research faworyzował textarea; plan przeszedł na CodeMirror 6 dla syntax highlighting i undo/redo.
- `context/archive/2026-06-16-draft-authoring-persistence/plan-brief.md` — explicit out of scope: „Rich WYSIWYG, split preview”; CodeMirror via `vue-codemirror6`.
- `context/archive/2026-06-16-draft-authoring-persistence/plan.md` — spec `AdrMarkdownEditor.client.vue` z `basicSetup`, bez toolbara.
- `context/archive/2026-06-16-adr-history-cards/plan.md` — `readonly` prop na tym samym komponencie dla `in_review`.
- `context/archive/2026-06-17-first-ai-review-annotations/plan-brief.md` — adnotacje w osobnym panelu, nie inline w edytorze.
- **Toolbar nigdy nie był rozważany** w archiwum — to naturalna ewolucja bez sprzeczności z MVP scope.

## Related Research

- Wcześniejsza rozmowa (exa-web-search): porównanie md-editor-v3, pd-editor-vue, Barkdown, Milkdown dla UX podobnego do Jiry.

## Open Questions

1. **Styling** — czy akceptowalny jest domyślny theme md-editor-v3, czy potrzebny dark-mode sync z `color-mode` / shadcn tokens?
2. **Preview** — czy włączyć `preview` na toolbara dla autorów ADR, skoro historycznie split preview był out of scope?
3. **Tabele i task lists** — czy ADR template wymaga `table` / `task` na toolbarze?
4. **Blur przy toolbar click** — czy w praktyce powoduje niechciane PATCH-e; jeśli tak, debounce lub `relatedTarget` check w handlerze.
5. **Usunięcie starych deps** — po migracji: czy usunąć `vue-codemirror6`, `codemirror`, `@codemirror/*` z `package.json`?

## Recommendation

**Wdrożyć md-editor-v3** jako implementację `AdrMarkdownEditor` z:

```vue
<MdEditor
  :id="'adr-editor'"
  :model-value="modelValue"
  :read-only="readonly"
  :toolbars="adrToolbars"
  no-upload-img
  @update:model-value="onUpdate"
  @on-blur="onBlur"
/>
```

oraz ewentualnie `:toolbars-exclude` jako druga warstwa bezpieczeństwa. Custom toolbar jest w pełni wspierany — usuwanie obrazków i innych niechcianych akcji to konfiguracja, nie fork biblioteki.

## External References

- [md-editor-v3 API (EN)](https://imzbf.github.io/md-editor-v3/en-US/api)
- [md-editor-v3 GitHub](https://github.com/imzbf/md-editor-v3)
- [Nuxt example](https://github.com/imzbf/md-editor-v3/tree/develop/example/nuxt)
- [noUploadImg / image upload issue #776](https://github.com/imzbf/md-editor-v3/issues/776)
- [Type definitions v6.4.1](https://cdn.jsdelivr.net/npm/md-editor-v3@6.4.1/lib/types/index.d.ts)
