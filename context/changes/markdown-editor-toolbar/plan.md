# Markdown Editor Toolbar + Preview Implementation Plan

## Overview

Replace the CodeMirror-based `AdrMarkdownEditor` with **md-editor-v3**, adding a Jira-like formatting toolbar, **preview toggle**, table/task list support, and **shadcn-aligned theming** with dark-mode sync. The component contract (`modelValue`, `readonly`, `update:modelValue`, `blur`) and the ADR page save-on-blur flow remain unchanged.

## Current State Analysis

`AdrMarkdownEditor.client.vue` wraps `vue-codemirror6` with markdown syntax highlighting. There is no toolbar and no preview. The only consumer is `frontend/app/pages/workspace/adr/[id].vue`, wrapped in `<ClientOnly>` with save-on-blur via `useAdrPersistence` and an `isDirty` guard.

Historical MVP scope excluded rich WYSIWYG and split preview (`context/archive/2026-06-16-draft-authoring-persistence/plan-brief.md`). This change is an intentional evolution: toolbar-assisted markdown editing with an optional preview toggle, not a Notion-style WYSIWYG.

## Desired End State

Authors editing a draft ADR see an md-editor-v3 toolbar (bold, lists, code, link, table, task, preview, etc.) with image upload disabled. Clicking **preview** toggles between source editing and rendered markdown. In `in_review` (readonly), the same component renders **MdPreview** only — no toolbar, formatted markdown visible. Editor chrome matches shadcn tokens (`border-input`, `bg-background`, `rounded-md`) and follows `@nuxtjs/color-mode` light/dark. All existing Vitest contracts pass; CodeMirror dependencies are removed.

### Key Discoveries

- Component contract at `frontend/app/components/adr/AdrMarkdownEditor.client.vue:5-18` is intentionally thin — internal swap is safe.
- Save chain: `@update:model-value` → `updateContent` (dirty) → `@blur` → `saveOnBlur` when `isReviewEditable && isDirty` (`useAdrPersistence.ts:18-23`).
- Styling precedent: wrapper uses semantic Tailwind tokens; library internals overridden via scoped `:deep()` (`AdrMarkdownEditor.client.vue:49-58`).
- md-editor-v3: `no-upload-img` + exclude `'image'` from toolbars disables image UI; `theme` prop accepts `'light' | 'dark'`; readonly display uses `MdPreview` + `preview.css`.

## What We're NOT Doing

- Image upload or paste-to-image UI (explicitly disabled)
- Mermaid, KaTeX, Prettier, save/github/catalog toolbar buttons
- Fullscreen mode
- Inline review annotations inside the editor (annotations stay in `AdrReviewAnnotations.vue`)
- Backend or API changes (content remains a markdown string)
- WYSIWYG editing (source markdown remains the storage format)
- Custom blur debounce or `relatedTarget` filtering (keep existing `isDirty` guard)
- MdCatalog / table-of-contents sidebar

## Implementation Approach

Three incremental phases: (1) swap implementation and toolbar config on `MdEditor`, (2) readonly `MdPreview` branch plus theme/CSS alignment, (3) test updates and dependency cleanup. Preserve the stable `AdrMarkdownEditor` public API so `[id].vue` needs no changes.

## Critical Implementation Details

**Readonly vs editable split:** When `readonly` is true, render `MdPreview` instead of `MdEditor`. Do not emit `blur` or `update:modelValue` in readonly mode (same as today). The page's `isReadOnly` guard on blur/input remains as defense in depth.

**Theme sync:** Bind `:theme="editorTheme"` where `editorTheme` is a computed from `useColorMode()` — `'dark'` when `colorMode.value === 'dark'`, else `'light'`. Apply the same theme to both `MdEditor` and `MdPreview`. Use a stable `id="adr-editor"` on both for SSR consistency.

**CSS imports:** Import `md-editor-v3/lib/style.css` for editable mode. Import `md-editor-v3/lib/preview.css` for preview rendering (both branches may need preview styles; import both in the component or a dedicated side-effect import — avoid duplicate global resets).

**Preview toggle:** Include `'preview'` in the toolbar whitelist. Users toggle via the built-in toolbar button (not split-by-default, not a separate tab).

## Phase 1: Core md-editor-v3 Migration

### Overview

Add `md-editor-v3`, replace CodeMirror internals with `MdEditor`, configure the ADR toolbar (including preview, table, task), disable image upload, and preserve the existing props/emits contract for editable mode.

### Changes Required:

#### 1. Add dependency

**File**: `frontend/package.json`

**Intent**: Add `md-editor-v3` (v6.4.1 or latest satisfying `minimumReleaseAge: 10080` in `pnpm-workspace.yaml`). Run `pnpm install` to refresh the lockfile.

**Contract**: New runtime dependency `md-editor-v3`; no CodeMirror removal yet (Phase 3).

#### 2. Toolbar configuration module

**File**: `frontend/app/components/adr/adr-editor-toolbars.ts` (new)

**Intent**: Centralize the ADR toolbar whitelist and excluded features so the component stays readable and the toolbar set is testable in isolation.

**Contract**: Export `adrToolbars` as `ToolbarNames[]` with this order and set:

- `bold`, `italic`, `strikeThrough`, `-`, `title`, `quote`, `unorderedList`, `orderedList`, `task`, `-`, `codeRow`, `code`, `link`, `table`, `=`, `preview`, `revoke`, `next`
- Must not include: `image`, `mermaid`, `katex`, `save`, `prettier`, `fullscreen`, `github`, `catalog`

#### 3. Migrate AdrMarkdownEditor (editable branch)

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`

**Intent**: Replace `vue-codemirror6` with `MdEditor` for the editable (`readonly === false`) path. Wire `v-model` through existing `onUpdate` readonly guard. Map `@on-blur` to emit `blur` when not readonly. Set `no-upload-img`, `:toolbars="adrToolbars"`, stable `id="adr-editor"`, `language="en-US"`, `preview-theme="github"`, `code-theme` appropriate for light/dark (e.g. `atom` / `github` — pick one pair and keep consistent). Retain wrapper classes: `min-h-[24rem] w-full overflow-hidden rounded-md border border-input text-sm`.

**Contract**: Props `modelValue: string`, `readonly?: boolean` (default `false`). Emits `update:modelValue`, `blur`. Editable path uses `MdEditor` only; readonly path deferred to Phase 2.

#### 4. Phase 1 scoped styling (minimal)

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`

**Intent**: Apply the same wrapper token classes as the current CodeMirror editor. Add initial `:deep()` rules for min-height on the editor content area (mirror current `24rem` minimum).

**Contract**: Root class `adr-markdown-editor` on wrapper; min-height preserved.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm install` completes cleanly
- `cd frontend && pnpm run typecheck` passes
- `cd frontend && pnpm run lint` passes

#### Manual Verification:

- Draft ADR page loads the new editor inside `<ClientOnly>` without console errors
- Toolbar shows formatting actions plus table, task, and preview (no image button)
- Bold/list/code/link/table/task insertions produce valid markdown in the source pane
- Preview toolbar button toggles between edit and preview views
- Typing emits content updates; blur triggers save when content was changed (existing behavior)
- Paste/drag image does not show upload UI (`no-upload-img`)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Readonly Preview + Theme Sync

### Overview

Add the `MdPreview` branch for readonly mode, synchronize md-editor `theme` with `@nuxtjs/color-mode`, and deepen CSS overrides so toolbar, editor surface, and preview pane match shadcn semantic tokens in light and dark mode.

### Changes Required:

#### 1. Readonly MdPreview branch

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`

**Intent**: When `readonly` is true, render `MdPreview` with `:model-value="modelValue"`, same `id`, `theme`, and `preview-theme` as the editable editor. Do not render toolbar. Suppress all emits (no `blur`, no `update:modelValue`).

**Contract**: `v-if="readonly"` → `MdPreview`; `v-else` → `MdEditor`. Import `md-editor-v3/lib/preview.css`.

#### 2. Color-mode theme binding

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`

**Intent**: Use `useColorMode()` to compute `editorTheme: 'light' | 'dark'` and pass it to both `MdEditor` and `MdPreview`. Toggling site theme via `ThemeToggle` should update editor chrome without remounting the page.

**Contract**: `:theme="editorTheme"` on both components; reactive to color-mode changes.

#### 3. shadcn token CSS overrides

**File**: `frontend/app/components/adr/AdrMarkdownEditor.client.vue` (scoped `:deep()` block)

**Intent**: Map md-editor-v3 internal surfaces to project CSS variables so the editor visually matches adjacent shadcn `Input` and layout chrome. Target at minimum: outer border/background, toolbar background/border, toolbar button hover/active, editor content background, preview pane background/text, focus ring color.

**Contract**: Use semantic variables (`var(--background)`, `var(--foreground)`, `var(--border)`, `var(--muted)`, `var(--accent)`, `var(--ring)`, `var(--radius)`) — not hard-coded hex. Overrides scoped under `.adr-markdown-editor :deep(...)`. Verify in both `:root` and `.dark` contexts.

#### 4. Readonly page UX check (no page code change expected)

**File**: `frontend/app/pages/workspace/adr/[id].vue`

**Intent**: Confirm existing `isReadOnly` wiring (`:readonly="isReadOnly"`) produces preview-only content for `in_review` ADRs without further page edits.

**Contract**: No required changes to `[id].vue` if `AdrMarkdownEditor` honors `readonly` internally.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run typecheck` passes
- `cd frontend && pnpm run lint` passes

#### Manual Verification:

- `in_review` ADR shows rendered markdown preview only (no toolbar, not editable)
- Light and dark mode: editor border, toolbar, and preview pane match surrounding shadcn UI
- Preview toggle in editable mode renders markdown consistent with readonly preview styling
- Theme toggle while on editor page updates md-editor theme immediately

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Tests & Dependency Cleanup

### Overview

Update Vitest stubs and assertions for the new implementation, remove obsolete CodeMirror packages, and run the full frontend verification suite.

### Changes Required:

#### 1. Component unit tests

**File**: `frontend/tests/adr-markdown-editor.test.ts`

**Intent**: Replace `CodeMirror` stub with `MdEditor` / `MdPreview` stubs (or a single stub per branch). Preserve the three behavioral contracts: readonly suppresses blur, editable emits blur on focus loss, readonly suppresses model updates. Add: editable mode renders `MdEditor` stub; readonly mode renders `MdPreview` stub (not `MdEditor`).

**Contract**: Same three tests updated; optional fourth test asserting component branch by `readonly` prop.

#### 2. Page integration test stub

**File**: `frontend/tests/adr-editor-page.test.ts`

**Intent**: Keep the `AdrMarkdownEditor` stub as a thin textarea (page-level contract unchanged) OR add a note that page tests remain decoupled from md-editor internals. No change required unless Phase 1–2 broke mount assumptions.

**Contract**: Existing page tests (`in_review` readonly UX, draft save-on-blur, etc.) continue to pass without modification to stub shape (`modelValue`, `readonly`, `update:modelValue`, `blur`).

#### 3. Remove CodeMirror dependencies

**File**: `frontend/package.json`

**Intent**: Remove packages no longer referenced after migration: `vue-codemirror6`, `codemirror`, `@codemirror/lang-markdown`, `@codemirror/language`, `@codemirror/state`, `@codemirror/view`. Run `pnpm install` to update lockfile.

**Contract**: `pnpm run build` and `pnpm run test` succeed with zero CodeMirror imports in `frontend/`.

#### 4. Toolbar config unit test (optional, recommended)

**File**: `frontend/tests/adr-editor-toolbars.test.ts` (new)

**Intent**: Assert `adrToolbars` includes `preview`, `table`, `task` and excludes `image`, `mermaid`, `katex`, `fullscreen`.

**Contract**: Pure array membership test; no component mount required.

### Success Criteria:

#### Automated Verification:

- `cd frontend && pnpm run test` passes
- `cd frontend && pnpm run typecheck` passes
- `cd frontend && pnpm run lint` passes
- `cd frontend && pnpm run build` passes
- Grep confirms no `codemirror` / `vue-codemirror6` imports under `frontend/`

#### Manual Verification:

- Full draft → edit → preview toggle → blur save → submit for review flow works
- `in_review` shows preview-only content; return to editable status restores toolbar editor
- No regressions on title field save-on-blur or review annotations panel

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Testing Strategy

### Unit Tests

- `AdrMarkdownEditor` readonly/editable emit guards (existing three cases)
- `adrToolbars` whitelist excludes image and heavy features
- Branch selection: `MdPreview` when readonly, `MdEditor` when editable

### Integration Tests

- `adr-editor-page.test.ts`: `in_review` readonly banner + disabled inputs; draft save-on-blur via title/editor stubs

### Manual Testing Steps

1. Open a draft ADR — verify toolbar, format text, toggle preview, blur to save
2. Insert table and task list via toolbar — confirm markdown syntax in source
3. Toggle site dark mode — editor chrome follows
4. Submit for review — editor becomes preview-only without toolbar
5. Confirm no image upload UI on paste or toolbar
6. Return ADR to editable status (if test data allows) — toolbar editor returns

## Performance Considerations

md-editor-v3 bundle is larger than bare CodeMirror (~604 KB unpacked per research). Acceptable tradeoff for toolbar + preview. Exclude `mermaid`, `katex`, `prettier` from toolbar to avoid loading optional heavy features. Keep `<ClientOnly>` wrapper on the page to avoid SSR hydration issues.

## Migration Notes

No data migration. ADR `content` field remains markdown string. Rollback: revert `AdrMarkdownEditor.client.vue` and restore CodeMirror deps from git history.

## References

- Research: `context/changes/markdown-editor-toolbar/research.md`
- Current editor: `frontend/app/components/adr/AdrMarkdownEditor.client.vue`
- Consumer page: `frontend/app/pages/workspace/adr/[id].vue`
- Persistence: `frontend/app/composables/useAdrPersistence.ts`
- Theme tokens: `frontend/app/assets/css/main.css`
- [md-editor-v3 API](https://imzbf.github.io/md-editor-v3/en-US/api)
- [Nuxt example](https://github.com/imzbf/md-editor-v3/tree/develop/example/nuxt)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands.

### Phase 1: Core md-editor-v3 Migration

#### Automated

- [x] 1.1 `cd frontend && pnpm install` completes cleanly — 2e4c084
- [x] 1.2 `cd frontend && pnpm run typecheck` passes — 2e4c084
- [x] 1.3 `cd frontend && pnpm run lint` passes — 2e4c084

#### Manual

- [x] 1.4 Draft ADR editor loads with toolbar, preview toggle, table/task, no image upload; blur save works — 2e4c084

### Phase 2: Readonly Preview + Theme Sync

#### Automated

- [x] 2.1 `cd frontend && pnpm run typecheck` passes — 4703ee1
- [x] 2.2 `cd frontend && pnpm run lint` passes — 4703ee1

#### Manual

- [x] 2.3 Readonly shows MdPreview only; light/dark theme matches shadcn UI — 4703ee1

### Phase 3: Tests & Dependency Cleanup

#### Automated

- [x] 3.1 `cd frontend && pnpm run test` passes
- [x] 3.2 `cd frontend && pnpm run typecheck` passes
- [x] 3.3 `cd frontend && pnpm run lint` passes
- [x] 3.4 `cd frontend && pnpm run build` passes
- [x] 3.5 No CodeMirror imports remain under `frontend/`

#### Manual

- [x] 3.6 Full draft → review → preview-only flow verified; no regressions
