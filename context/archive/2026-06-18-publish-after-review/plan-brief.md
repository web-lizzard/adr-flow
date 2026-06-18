# Publish After Review — Plan Brief

> Full plan: `context/changes/publish-after-review/plan.md`
> Research: `context/changes/publish-after-review/research.md`

## What & Why

S-05 completes the north-star flow: after AI review, the user edits their ADR in `after_review` and publishes it as `proposed` without re-triggering review. Editing in `after_review` already works (S-04); the missing piece is the publish transition end-to-end.

## Starting Point

Domain primitives exist (`AdrStatus.PROPOSED`, `ADRPublished` event, event-store deserialization). Backend allows editing in `after_review` and `proposed` (blocks only `in_review`). Frontend editor, blur/beacon save, review panel, and submit-for-review wiring are done. No `publish_adr` command, `mark_proposed` projection, API route, Publish button, or publish tests exist.

## Desired End State

User completes `draft` → `in_review` → `after_review` → `proposed` in one session. Clicking **Publish** in `after_review` transitions to `proposed` synchronously. Badge updates, toast confirms success, editor stays editable, review annotations remain visible when present, and status-aware helper copy replaces the generic draft message.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| -------- | ------ | ---------------- | ------ |
| Proposed editing | Remain editable | FR-005 permits editing except `in_review`; backend already allows it | Plan |
| Review panel after publish | Keep when annotations exist | Existing `showReviewPanel` logic; preserves review context | Plan |
| Helper copy | Status-aware per state | Avoids misleading "Draft changes save…" in `after_review`/`proposed` | Plan |
| Publish feedback | Status badge + toast | User wants explicit confirmation beyond badge alone | Plan |
| Publish in-flight UX | Mirror submit (disable editor, save-if-dirty) | Consistent with existing submit pattern; prevents race conditions | Plan |
| HTTP response | `204` + client reload | Matches submit pattern (`void` + `load(id)`); publish is sync | Research |
| Test depth | Command + projection + API + frontend unit | Covers illegal transitions without full lifecycle integration test | Plan |
| Architecture | Sync command with `mark_processed` | Publish emits no async work — unlike submit-for-review | Research |

## Scope

**In scope:**

- `mark_proposed` projection (preserves review metadata)
- `PublishAdrCommand` + handler with `after_review` guard
- `POST /api/adrs/{id}/publish` (204)
- Bootstrap + dependency wiring
- Backend tests (legal + illegal transitions, ownership)
- Frontend: API → store → composable → Publish button
- Minimal toast infrastructure for publish success
- Status-aware helper copy
- Frontend unit tests

**Out of scope:**

- Re-review or async dispatch on publish
- Full automated lifecycle integration test
- `proposed` read-only mode
- Post-MVP statuses (`accepted`, `superseded`)
- Returning ADR body from publish endpoint

## Architecture / Approach

Mirror the submit-for-review vertical slice at every layer, but synchronous: command appends `ADRPublished`, calls `mark_proposed`, marks event processed in the same transaction, returns 204. Frontend copies `submitForReview` wiring with a separate **Publish** label (not "Publish for review"). No `EventDispatcher` registration for `ADRPublished`.

```
after_review ──PublishAdr──► ADRPublished ──mark_proposed──► proposed (sync, 204)
```

## Phases at a Glance

| Phase | What it delivers | Key risk |
| ----- | ---------------- | -------- |
| 1. Backend publish transition | Command, projection, API, tests | `mark_proposed` accidentally clearing review metadata |
| 2. Frontend publish CTA + UX | Button, toast, copy, tests | Toast infra is net-new; keep scope minimal |

**Prerequisites:** S-04 done (after_review editing + annotations)
**Estimated effort:** ~2 implementation sessions across 2 phases

## Open Risks & Assumptions

- Toast component must be added via shadcn-nuxt — first toast usage in the app; keep scoped to publish success.
- `mark_proposed` SQL must not copy `mark_in_review`'s review-field clearing behavior.
- Manual E2E depends on AI review completing in dev environment (existing S-04 polling).

## Success Criteria (Summary)

- User publishes from `after_review` to `proposed` without re-review
- Illegal publish attempts (wrong status, wrong owner) return appropriate errors
- Full north-star demo works manually: draft → review → edit → publish with toast and editable `proposed` state
