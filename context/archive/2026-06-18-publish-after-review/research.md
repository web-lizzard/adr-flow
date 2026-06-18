---
date: 2026-06-18T12:00:00Z
researcher: Cursor Agent
git_commit: 8355e789dd2909bf716d63b1a251c161bb16f320
branch: main
repository: web-lizzard/adr-flow
topic: "S-05 Publish After Review — implementation readiness and gaps"
tags: [research, codebase, publish-after-review, adr-lifecycle, north-star]
status: complete
last_updated: 2026-06-18
last_updated_by: Cursor Agent
---

# Research: S-05 Publish After Review

**Date**: 2026-06-18T12:00:00Z
**Researcher**: Cursor Agent
**Git Commit**: `8355e789dd2909bf716d63b1a251c161bb16f320`
**Branch**: main
**Repository**: web-lizzard/adr-flow

## Research Question

What exists in the codebase today for S-05 (`publish-after-review`), what did S-04 defer, and what must be built to complete the north-star flow (`draft` → `in_review` → `after_review` → `proposed`)?

## Summary

S-05 is the **north-star slice** that completes Success Criterion #1. Prerequisites are met: S-04 is done and users can reach `after_review` with annotations. **Roughly half the slice is already implemented** — editing in `after_review` without re-review works end-to-end (backend `update_adr_content`, frontend editor page, persistence composable). **The publish transition is entirely missing**: no `publish_adr` command, no `mark_proposed` projection, no API route, no frontend Publish button or store method, and no publish tests.

Implementation should follow the existing **`submit_adr_for_review` vertical slice** as a template, but as a **synchronous** command (like `create_adr` / `update_adr_content`) with `mark_processed` — publish does not enqueue async AI work.

## Detailed Findings

### Product requirements (PRD)

| Ref | Requirement |
|-----|-------------|
| **US-01** | Full one-session flow ending at `proposed`; publish from `after_review` without additional review |
| **US-04** | Edit in `after_review` preserves status; "Publish" → `proposed` without re-review |
| **FR-005** | Edit markdown in any status **except** `in_review` |
| **FR-007** | Four-status lifecycle: `draft` → `in_review` → `after_review` → `proposed` |
| **FR-009** | "Publish" from `after_review` → `proposed`; no AI re-review |

Definition of done (from roadmap issue proposal):

- [ ] Edit markdown inline in `after_review` — **largely done**
- [ ] Edits persist (save-on-blur / save-on-unload) — **done** (S-02/S-04)
- [ ] Status remains `after_review` during edits — **done** (no re-review path)
- [ ] "Publish" → `proposed` — **not built**
- [ ] E2E demo through `proposed` — **blocked on publish**

### State machine (target)

```
draft ──SubmitAdrForReview──► in_review ──AIReviewCompleted──► after_review
  ▲                                    │
  │ UpdateAdrContent (edit)            │ read-only
  └──────── after_review ◄─────────────┘
              │ UpdateAdrContent (edit, no re-review)  ✅ implemented
              │ PublishAdr / ADRPublished              ❌ missing
              ▼
           proposed
```

### Backend — what exists

| Component | Location | Status |
|-----------|----------|--------|
| `AdrStatus.PROPOSED` | `backend/domain/adr/value_objects.py:8-12` | ✅ |
| `ADRPublished` event | `backend/domain/adr/events.py:39-40` | ✅ (payload: `adr_id` only) |
| Event-store type registry | `backend/infrastructure/adapters/persistence/event_store.py:30` | ✅ |
| Edit in `after_review` | `backend/application/commands/update_adr_content.py:47-53` | ✅ (blocks only `in_review`) |
| Submit-for-review pattern | `backend/application/commands/submit_adr_for_review.py` | ✅ (template for publish) |
| List/read `proposed` ADRs | `backend/tests/infrastructure/adapters/persistence/test_adr_repository.py` | ✅ (seeded status) |

### Backend — gaps

| Component | Expected location | Notes |
|-----------|-------------------|-------|
| `PublishAdrCommand` + handler | `backend/application/commands/publish_adr.py` | Per `application-architecture.md` S-05 row |
| `mark_proposed` projection | `backend/application/ports/adr_projection.py` + `SqlAdrProjection` | Sets `status = 'proposed'`, bumps `updated_at`; keep review metadata |
| `ADRPublished` in sync projection types | `event_store.py` `SYNC_PROJECTION_EVENT_TYPES` | Currently only `UserRegistered`, `ADRCreated`, `ADRContentUpdated` |
| API route | `POST /api/adrs/{adr_id}/publish` in `adr.py` | Sync `200`/`204` (not `202`) |
| Bootstrap + dependency wiring | `bootstrap.py`, `dependencies.py` | Mirror submit handler registration |
| Tests | command, projection, API integration | Zero publish tests today |

**Recommended publish handler logic** (mirrors submit):

1. Load ADR via `find_by_id_for_owner` → `AdrNotFound` if missing
2. Guard: `existing.status == after_review` only → `DomainError` otherwise
3. Emit `ADRPublished` with `occurred_at`
4. UoW: `append` event + `mark_proposed` projection + `mark_processed` (sync pattern from `create_adr.py`)

**Status guard message** (follow submit convention): e.g. `"ADR can only be published from after_review status"`.

**Illegal transitions to test** (test-plan risk #2):

- Publish from `draft`, `in_review`, `proposed`
- `draft` → `proposed` skip (no endpoint today, but command guard is required)

### Frontend — what exists

| Component | Location | Status |
|-----------|----------|--------|
| `after_review` editable | `frontend/app/pages/workspace/adr/[id].vue:21-23` | ✅ (`isReadOnly` only for `in_review`) |
| Review panel in `after_review` | `[id].vue:27-37`, `AdrReviewAnnotations.vue` | ✅ |
| Blur/beacon save in `after_review` | `useAdrPersistence.ts:12-16` | ✅ |
| `proposed` badge styling | `AdrStatusBadge.vue:21-24` | ✅ |
| Submit-for-review wiring | `useApi` → store → `useAdr` → page | ✅ (pattern to copy) |

### Frontend — gaps

| Component | Notes |
|-----------|-------|
| `publishAdr(id)` in `frontend/composables/useApi.ts` | `POST /adrs/{id}/publish` |
| `publish(id)` in `frontend/app/stores/adr.ts` | API call + `load(id)` + loading flag |
| `publish` export in `useAdr.ts` | Re-export from store |
| Publish button on `[id].vue` | `showPublishButton` when `status === "after_review"` |
| `onPublish` handler | Save-if-dirty → `publish(id)` → error state |
| Tests | `adr.store.test.ts`, `adr-editor-page.test.ts` |
| `proposed` post-publish UX | **Open decision** — FR-005 allows edit in `proposed`; no slice exercises it |

**Copy distinction:** Draft CTA is **"Publish for review"** (`[id].vue:156`); S-05 needs a separate **"Publish"** label for `after_review` → `proposed` to avoid confusion.

### Submit-for-review pattern (reference implementation)

```
submit_adr_for_review.py  →  POST /adrs/{id}/submit-review  →  202 Accepted
  guard: draft only
  event: ADRSubmittedForReview
  projection: mark_in_review
  async: RunAiReviewHandler (no mark_processed)

publish_adr.py (to build)  →  POST /adrs/{id}/publish  →  200/204
  guard: after_review only
  event: ADRPublished
  projection: mark_proposed
  sync: mark_processed (like create_adr)
```

Frontend stack to mirror:

```
useApi.submitAdrForReview  →  store.submitForReview  →  useAdr  →  [id].vue onSubmitForReview
```

## Code References

- `backend/domain/adr/events.py:39-40` — `ADRPublished` event (minimal payload)
- `backend/domain/adr/value_objects.py:8-12` — four-status enum including `proposed`
- `backend/application/commands/submit_adr_for_review.py:58-65` — status guard pattern for commands
- `backend/application/commands/update_adr_content.py:47-53` — blocks edit only in `in_review`
- `backend/infrastructure/api/routers/adr.py:68-108` — submit-review endpoint (API template)
- `frontend/app/pages/workspace/adr/[id].vue:21-26` — read-only + submit button visibility
- `frontend/app/pages/workspace/adr/[id].vue:99-119` — `onSubmitForReview` handler pattern
- `frontend/composables/useApi.ts:104-108` — `submitAdrForReview` API client
- `frontend/app/stores/adr.ts:183-191` — `submitForReview` store method
- `frontend/tests/adr-editor-page.test.ts:203-231` — confirms `after_review` editable, submit hidden

## Architecture Insights

- **Commands own transitions.** Routers never set `adrs.status` directly; projection methods (`mark_in_review`, `apply_review_result`, future `mark_proposed`) apply event outcomes.
- **No aggregate lifecycle methods.** F-02 guardrail (`test_vocabulary_only.py`) forbids `publish()` on the ADR dataclass; validation lives in command handlers.
- **Re-review is structurally impossible today.** Only `ADRSubmittedForReview` registers async dispatch; idempotent skip when already `after_review` in `run_ai_review.py`.
- **S-05 is narrower than it sounds.** Most US-04 / FR-005 work landed in S-02/S-04; S-05 is primarily the publish command + UI CTA + tests.
- **Sync vs async split:** submit-review returns `202` and defers AI work; publish should be fully synchronous.

## Historical Context (from prior changes)

- `context/archive/2026-06-17-first-ai-review-annotations/plan.md` — S-04 explicitly deferred publishing to `proposed`, `PublishAdr` command, and "Publish" CTA; delivered `after_review` editing, annotation panel, and polling instead.
- `context/changes/persistence-scaffold/research.md` — documents `PublishAdr` → `ADRPublished`, forward-only machine, and FR-009 no re-review invariant.
- `context/foundation/application-architecture.md:188` — names `commands/publish_adr.py` as the S-05 application addition.
- `context/foundation/roadmap.md:129-139` — S-05 status `proposed`; prerequisite S-04 `done`.
- `context/foundation/test-plan.md` — Phase 1 risk #2 (illegal status transitions) is the primary test-plan driver for S-05.

## Related Research

- `context/changes/persistence-scaffold/research.md` — domain model, event vocabulary, publish command design
- `context/archive/2026-06-17-first-ai-review-annotations/plan.md` — S-04 scope boundary and S-05 deferrals

## Open Questions

1. **`proposed` editing UX.** FR-005 permits editing in any status except `in_review`, but no slice exercises `proposed` edits. Should the editor become read-only after publish, or remain editable with blur-save? Recommend deciding in `/plan` and adding one explicit test.
2. **Review panel after publish.** Should `AdrReviewAnnotations` remain visible in `proposed`, or hide? Currently shown when `status === "after_review"` OR annotations exist — post-publish behavior undefined.
3. **HTTP response shape.** `204 No Content` vs `200` with updated ADR body — follow existing submit pattern (`void` + client reload) for consistency.
4. **Ready for `/plan`?** Roadmap backlog still says `no` pending S-04; S-04 is now `done` on `main`. This change can advance to `/plan`.

## Suggested implementation order

1. `mark_proposed` on projection port + SQL adapter (+ fake stubs in tests)
2. `publish_adr.py` command handler with guards and `mark_processed`
3. Add `ADRPublished` to `SYNC_PROJECTION_EVENT_TYPES`
4. API route + bootstrap + dependency injection
5. Backend tests (command, projection, API — legal + illegal transitions + ownership)
6. Frontend: `publishAdr` → store → `useAdr` → page button + tests
7. Manual E2E: login → draft → review → fix → publish as `proposed`
