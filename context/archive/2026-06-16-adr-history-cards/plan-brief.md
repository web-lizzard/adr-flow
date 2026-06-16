# ADR History Cards — Plan Brief

> Full plan: `context/changes/adr-history-cards/plan.md`

## What & Why

Users need to return days later and pick up where they left off — browsing their ADR history proves the product has lasting value, not just a one-shot editor. S-03 delivers FR-013: a card view on the workspace showing title, status, and last-edited timestamp, with the ability to reopen any ADR for viewing or editing where status permits.

## Starting Point

S-02 (done) provides create/edit/save, `/workspace/adr/[id]` editor route, `AdrSummary` DTO, and backend owner-scoped queries — but the workspace is create-only and there is no `GET /api/adrs` list endpoint. Search exists solely for title-uniqueness validation during create.

## Desired End State

A logged-in user opens `/workspace`, sees their ADR cards in a grid below the create form (newest-edited first), clicks any card to open the editor, and uses a back link to return to refreshed cards. `in_review` ADRs open read-only with a clear banner; all other statuses remain editable per FR-005.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Workspace layout | Cards below create form | Preserves S-02 create-first flow; history revealed on scroll | Plan |
| Sort order | `updated_at` descending | Surfaces most recently touched work first | Plan |
| `in_review` UX | Read-only editor + status banner | Prevents surprise save failures; matches FR-005 upfront | Plan |
| Empty history | Inline message in history section | Sets expectation without extra design assets | Plan |
| Editor navigation | "Back to workspace" link | Explicit affordance to return to card list | Plan |
| List refresh | Re-fetch on workspace visit | Cards reflect edits after returning from editor | Plan |
| Status display | Color-coded badges | Clear at-a-glance indicators per US-02 | Plan |
| Testing depth | Backend API + store + component tests | Covers contracts without E2E infra | Plan |
| List API | Dedicated `GET /api/adrs` | Search endpoint cannot list-all; PRD forbids search UI | Plan |

## Scope

**In scope:** Backend list query + endpoint; frontend card grid on workspace; status badges; reopen via existing editor route; read-only `in_review` mode; back navigation; automated tests at API/store/component level.

**Out of scope:** List filtering/search UI; soft-delete (S-06); AI review / status transitions (S-04/S-05); pagination; E2E browser tests; schema migration.

## Architecture / Approach

```
Workspace page                    Editor page
┌─────────────────────┐          ┌─────────────────────┐
│ Create ADR form     │          │ ← Back to workspace │
│ ─────────────────── │  click   │ Status badge        │
│ Your ADRs (grid)    │ ───────► │ Title + Editor      │
│  [AdrCard × N]      │          │ (read-only if       │
└─────────┬───────────┘          │  in_review)         │
          │ GET /api/adrs        └─────────────────────┘
          ▼
   ListAdrsQuery → SqlAdrRepository.list_for_owner
   (user_id + is_deleted=false, ORDER BY updated_at DESC)
```

Reuses existing `AdrSummary` DTO and S-02 editor/save infrastructure. No new tables.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend List API | `GET /api/adrs` with tests | Route ordering vs `/{adr_id}` |
| 2. Frontend List Plumbing | `listAdrs()` + store `fetchList` | Store state collision with single-ADR editor |
| 3. Card UI & Workspace | `AdrCard` grid + empty state | Date formatting consistency |
| 4. Status-Aware Editor | Read-only `in_review` + back nav | CodeMirror readonly prop behavior |

**Prerequisites:** S-02 merged (done); authenticated user with ADRs for manual testing.
**Estimated effort:** ~2 sessions across 4 phases.

## Open Risks & Assumptions

- `in_review` ADRs can only be manually tested until S-04 adds status transitions (DB seed or test fixture acceptable).
- Unpaginated list is acceptable at MVP scale (< 100 ADRs per user per PRD).
- `vue-codemirror6` supports readonly mode via CodeMirror extensions — verify during Phase 4 implementation.

## Success Criteria (Summary)

- Logged-in user sees all owned ADRs as cards with title, status, and last-edited
- Clicking a card opens the correct ADR; `in_review` is read-only
- Returning to workspace shows updated card data after edits
- Other users' ADRs never appear in the list
