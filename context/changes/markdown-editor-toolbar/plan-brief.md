# Markdown Editor Toolbar + Preview — Plan Brief

> Full plan: `context/changes/markdown-editor-toolbar/plan.md`
> Research: `context/changes/markdown-editor-toolbar/research.md`

## What & Why

Replace the raw CodeMirror ADR editor with **md-editor-v3**: a Jira-like formatting toolbar, optional **preview toggle**, and styling aligned with the app's shadcn/Tailwind design system. Authors get faster markdown formatting without changing the storage format or backend contract.

## Starting Point

`AdrMarkdownEditor.client.vue` wraps `vue-codemirror6` with no toolbar and no preview. The ADR detail page (`[id].vue`) uses save-on-blur with an `isDirty` guard. Historical MVP excluded split preview; this change adds preview as an explicit product decision.

## Desired End State

Draft authors see a toolbar (bold, lists, code, link, **table**, **task**, **preview**) and can toggle preview on demand. In `in_review`, the editor shows **rendered markdown only** (`MdPreview`, no toolbar). Chrome matches shadcn tokens and follows dark mode. CodeMirror dependencies are removed; tests pass.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Editor library | md-editor-v3 | Vue 3 native, toolbar whitelist, markdown string contract | Research |
| Preview UX | Toolbar toggle | Built-in preview button; no permanent split view | Plan |
| Readonly (`in_review`) | MdPreview only | Clean read-only rendering without toolbar noise | Plan |
| Styling depth | Token sync + `:deep()` | Match shadcn via CSS variables; sync `theme` with color-mode | Plan |
| Toolbar extras | table + task lists | ADR templates benefit from structured content | Plan |
| Image upload | Disabled (`no-upload-img` + exclude `image`) | Out of scope; three-layer disable per research | Research |
| Blur / save | Existing `isDirty` guard | No new blur filtering; guard already prevents spurious saves | Plan |
| CodeMirror deps | Remove after migration | md-editor-v3 bundles CodeMirror internally | Plan |

## Scope

**In scope:** `AdrMarkdownEditor` migration, toolbar config, preview toggle, readonly `MdPreview`, theme/CSS alignment, test updates, CodeMirror dependency removal.

**Out of scope:** Image upload, mermaid/KaTeX, fullscreen, WYSIWYG, inline annotations, backend changes, MdCatalog sidebar, custom blur debounce.

## Architecture / Approach

Keep the stable `AdrMarkdownEditor` API (`modelValue`, `readonly`, `update:modelValue`, `blur`). Internally: `MdEditor` when editable (toolbar + preview toggle), `MdPreview` when readonly. `useColorMode()` drives `:theme`. Scoped `:deep()` CSS maps md-editor surfaces to `--background`, `--border`, `--ring`, etc. Page wiring in `[id].vue` unchanged.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Core migration | md-editor-v3, toolbar, preview toggle, no image upload | Preview/blur interaction on toolbar click |
| 2. Preview + theming | MdPreview readonly, color-mode sync, shadcn CSS overrides | md-editor default CSS fighting token overrides |
| 3. Tests & cleanup | Vitest updates, remove CodeMirror deps, build verify | Test stubs tightly coupled to old CodeMirror |

**Prerequisites:** Research complete; `minimumReleaseAge` policy satisfied for md-editor-v3.
**Estimated effort:** ~2–3 focused sessions across 3 phases.

## Open Risks & Assumptions

- md-editor-v3 default CSS may need iterative `:deep()` tuning to match shadcn in both themes.
- Bundle size increases vs bare CodeMirror (acceptable for toolbar + preview).
- `preview-theme="github"` is a sensible default for technical docs; adjust in Phase 2 if contrast is off.
- Toolbar click blur is mitigated by `isDirty` guard; monitor for unexpected PATCH attempts in manual testing.

## Success Criteria (Summary)

- Authors format ADR markdown via toolbar and toggle preview without leaving the page.
- `in_review` ADRs display rendered markdown only, styled consistently with the app.
- All frontend tests, lint, typecheck, and build pass; CodeMirror deps removed.
