# Proposed GitHub Issues — Roadmap Foundations & Slices

> **Status:** split into `github-issues/*.md`; run `github-issues/create.sh` to push to GitHub (requires `GH_TOKEN` with Issues write)
>
> Source: `context/foundation/roadmap.md` (v1, updated 2026-06-10)

| ID | Labels | Body file |
|---|---|---|
| F-02 | `foundation`, `core` | `github-issues/F-02-persistence-scaffold.md` |
| F-01 | `foundation`, `core` | `github-issues/F-01-review-quality-checks.md` |
| S-01 | `slice`, `core` | `github-issues/S-01-account-access.md` |
| S-02 | `slice`, `core` | `github-issues/S-02-draft-authoring-persistence.md` |
| S-04 | `slice`, `core` | `github-issues/S-04-first-ai-review-annotations.md` |
| S-05 | `slice`, `core` | `github-issues/S-05-publish-after-review.md` |
| S-03 | `slice`, `history` | `github-issues/S-03-adr-history-cards.md` |
| S-06 | `slice`, `history` | `github-issues/S-06-remove-adr-from-active-list.md` |
>
> Eight issues below map 1:1 to roadmap items F-02, F-01, and S-01 through S-06. Create them only after review; use the `gh issue create` snippets at the bottom when ready.

## Conventions (proposed)

| Field | Proposal |
|---|---|
| **Labels** | `foundation` or `slice`, plus track `core` or `history` |
| **Label matrix** | F-02, F-01, S-01, S-02, S-04, S-05 → `foundation,core` or `slice,core`; S-03, S-06 → `slice,history` |
| **Issue linking** | Use `Blocked by #…` in the body (or GitHub's blocked-by field) for prerequisite issues once numbers exist |
| **Planning** | Items marked **Ready for `/plan`** can start with `/plan <change-id>` before implementation |

### Dependency order (create/link in this sequence)

```
F-02 ──┬──► S-01 ──► S-02 ──┬──► S-04 ──► S-05  (north star)
       │                     └──► S-03 ──► S-06
F-01 ─────────────────────────────► S-04
```

### Parallel tracks

- **Stream A** (persistence & core loop): F-02 → S-01 → S-02 → S-04 → S-05
- **Stream B** (review quality): F-01 (parallel with F-02; joins at S-04)
- **Stream C** (history & lifecycle): S-03 → S-06 (after S-02)

---

## Issue 1 — F-02: Persistence Scaffold

| Field | Value |
|---|---|
| **Title** | Add Postgres driver, migrations, and initial User/ADR schema |
| **Labels** | `foundation`, `core` |
| **Body file** | `github-issues/F-02-persistence-scaffold.md` |
| **Roadmap ID** | F-02 |
| **Change ID** | `persistence-scaffold` |
| **Ready for `/plan`** | yes |
| **Blocked by** | — |

### Body

```markdown
## Summary

Foundation slice: wire application persistence so users and ADRs can be stored with per-user ownership, lifecycle status, and soft-delete support.

**Outcome:** Postgres driver, migration tooling, and initial schema contract for `User` and `ADR` entities are in place — including per-user ownership (`user_id`), the four-status lifecycle field, markdown content storage, timestamps, and a soft-delete flag for FR-015.

## Why now

Baseline reports Data as **partial** — Postgres exists in devcontainer/deploy but the backend has no driver, ORM, models, or migrations. Without tables and migrations, no other stream can store users or ADRs.

## Scope

- Add Postgres driver and migration tooling to the backend
- Define minimal `User` and `ADR` schema contract (not a complete data layer)
- Include: `user_id` ownership, four ADR statuses (`draft`, `in_review`, `after_review`, `proposed`), markdown content, timestamps, soft-delete flag

## Out of scope

- Feature routers, auth, or UI — vertical slices integrate persistence through real user behavior
- Full repository/query abstractions beyond what foundations need

## PRD references

- NFR: Per-user data isolation
- NFR: Data retention
- NFR: No draft loss
- Access Control

## Unlocks

S-01, S-02, S-03, S-06 — every slice that reads or writes application state

## Risks

Sequenced first because infra exists but application persistence does not. Scope is the minimal schema contract; vertical slices still own integration through user flows.

## Definition of done

- [ ] Backend can connect to Postgres in local dev (devcontainer)
- [ ] Migration tooling runs cleanly on fresh and existing DB
- [ ] `User` and `ADR` tables match the lifecycle and ownership contract
- [ ] Soft-delete column present for later FR-015 exercise in S-06

## Planning

Run `/plan persistence-scaffold` before implementation.
```

---

## Issue 2 — F-01: Review Quality Checks

| Field | Value |
|---|---|
| **Title** | Add review-quality checks for required-section and actionability guardrails |
| **Labels** | `roadmap`, `foundation`, `stream-b` |
| **Milestone** | MVP — Core loop |
| **Roadmap ID** | F-01 |
| **Change ID** | `review-quality-checks` |
| **Ready for `/plan`** | yes |
| **Blocked by** | — |

### Body

```markdown
## Summary

Foundation slice: add a minimal verification harness so AI review output can be checked against PRD guardrails before the first review loop is treated as useful.

**Outcome:** Review output can be checked against required-section and actionability guardrails — a minimal verification harness, not a full review engine.

## Why now

This is the product wedge. Under the `speed` goal, invest just enough to clear the guardrail, then S-04 integrates it through real user behavior. Independent of persistence — can run in parallel with F-02.

## Scope

- Checks that review output detects missing required ADR sections (context, options, decision, status, consequences)
- Checks that each detected issue carries at least one concrete corrective action
- Harness suitable for automated verification (fixtures + assertions), not production UI

## Guardrails (from PRD)

- ≥80% of AI reviews correctly detect missing required sections
- Every flagged issue has an associated concrete corrective action proposal

## PRD references

- NFR: Section gap detection accuracy
- NFR: Annotation actionability

## Unlocks

S-04, S-05, and verification path for PRD guardrails on AI annotations

## Risks

Product must not mistake *any* annotation output for *useful* annotation output. Keep scope minimal under `speed`.

## Definition of done

- [ ] Harness accepts sample review output and asserts section-gap coverage
- [ ] Harness asserts actionability (corrective action per issue)
- [ ] Documented threshold / fixture set aligned with ≥80% guardrail intent
- [ ] Runnable in CI or local test suite without DB dependency

## Planning

Run `/plan review-quality-checks` before implementation. Can proceed in parallel with F-02.
```

---

## Issue 3 — S-01: Account Access

| Field | Value |
|---|---|
| **Title** | Let users register, log in, and reach a protected ADR workspace |
| **Labels** | `roadmap`, `slice`, `stream-a` |
| **Milestone** | MVP — Core loop |
| **Roadmap ID** | S-01 |
| **Change ID** | `account-access` |
| **Ready for `/plan`** | no (requires F-02) |
| **Blocked by** | F-02 (#TBD) |

### Body

```markdown
## Summary

Vertical slice: self-service registration and login with JWT, plus protected routes so each user reaches an isolated ADR workspace.

**Outcome:** User can register, log in, and reach a protected per-user ADR workspace.

## User story

**US-03:** Given a person who has never had an account, when they register with email and password, then their account is created and they can use the application immediately (no email verification in MVP).

## Functional requirements

- **FR-001:** Self-service signup with email and password
- **FR-003:** Login with email and password (no explicit logout in MVP; session expiry suffices)

## Access control

- Per-user data isolation — no cross-user ADR access
- Unauthorized access to protected routes redirects to login

## Prerequisites

- F-02 (`persistence-scaffold`) — `User` entity and DB layer must exist

## PRD references

- US-03, FR-001, FR-003
- Access Control
- NFR: Per-user data isolation

## Risks

Every ADR capability is per-user; weak access boundaries undermine all later slices. This slice wires registration, login, JWT, and route guards — not the schema itself.

## Definition of done

- [ ] User can register with email + password and land in the app without email verification
- [ ] User can log in with email + password
- [ ] Protected frontend routes redirect unauthenticated users to login
- [ ] API enforces authentication and per-user isolation on ADR endpoints (as added in later slices)
- [ ] Passwords stored securely (hashed, not plaintext)

## Planning

Run `/plan account-access` after F-02 is merged.
```

---

## Issue 4 — S-02: Draft Authoring & Persistence

| Field | Value |
|---|---|
| **Title** | Let users create and safely save ADR drafts from the starter template |
| **Labels** | `roadmap`, `slice`, `stream-a` |
| **Milestone** | MVP — Core loop |
| **Roadmap ID** | S-02 |
| **Change ID** | `draft-authoring-persistence` |
| **Ready for `/plan`** | no (requires S-01) |
| **Blocked by** | S-01 (#TBD) |

### Body

```markdown
## Summary

Vertical slice: create ADRs from the fixed markdown starter template, edit in a web editor, and persist drafts reliably.

**Outcome:** User can create an ADR from the starter template, edit markdown, and recover saved draft content after leaving or refreshing.

## User story

Part of **US-01** (create ADR from template, fill content) — full US-01 completes in S-04/S-05.

## Functional requirements

- **FR-004:** New ADR from standardized markdown template with headings: `## Context`, `## Options`, `## Decision`, `## Status`, `## Consequences`
- **FR-005:** Edit markdown in web editor (any status except `in_review` — relevant once review exists)
- **FR-006:** Persist edits via save-on-blur and save-on-unload (no continuous autosave in MVP)

## Starter template (structural contract for AI review)

```markdown
## Context

## Options

## Decision

## Status

## Consequences
```

## Prerequisites

- S-01 (`account-access`) — authenticated per-user workspace
- F-02 schema — ADR entity with `draft` status and markdown content

## PRD references

- US-01, FR-004, FR-005, FR-006
- NFR: No draft loss

## Open question

Does save-on-blur + save-on-unload suffice against draft loss? (Owner: user; gates this slice only if QA finds an unload edge case.)

## Risks

First real ADR state on top of F-02 schema. If persistence is unreliable, the later review loop hides the most important failure.

## Definition of done

- [ ] Logged-in user can create a new ADR from the starter template
- [ ] User can edit markdown in the web editor while ADR is in `draft`
- [ ] Content persists on save-on-blur
- [ ] Content persists on tab close / refresh via save-on-unload
- [ ] User can return in a new session and recover the latest saved draft

## Planning

Run `/plan draft-authoring-persistence` after S-01 is merged.
```

---

## Issue 5 — S-04: First AI Review Annotations

| Field | Value |
|---|---|
| **Title** | Let users submit a draft and receive actionable AI review annotations |
| **Labels** | `roadmap`, `slice`, `stream-a`, `stream-b` |
| **Milestone** | MVP — Core loop |
| **Roadmap ID** | S-04 |
| **Change ID** | `first-ai-review-annotations` |
| **Ready for `/plan`** | no (requires S-02, F-01) |
| **Blocked by** | S-02 (#TBD), F-01 (#TBD) |

### Body

```markdown
## Summary

Vertical slice: submit a draft for AI review and display actionable annotations when the ADR reaches `after_review`.

**Outcome:** User can submit a draft for AI review and see actionable missing-section, inconsistency, and conciseness annotations in `after_review`.

## User story

Part of **US-01** — user clicks "Publish for review", waits for review, reads annotations, then edits in `after_review` (publish flow completes in S-05).

## Functional requirements

- **FR-007:** Advance ADR through `draft` → `in_review` → `after_review` → `proposed` (this slice covers through `after_review`)
- **FR-008:** "Publish for review" transitions `draft` → `in_review`; AI review runs exactly once per ADR
- **FR-010:** Annotations for missing required sections
- **FR-011:** Annotations for content inconsistencies
- **FR-012:** Conciseness analysis with actionable shortening suggestions

## Business logic (review I/O)

**Input:** ADR markdown as published for review (five required section headings).

**Output:** Annotations for (a) missing/empty sections, (b) inconsistencies with location, (c) fragments to shorten with proposed wording.

**When visible:** After transition from `in_review` to `after_review`, inline in the editor.

## Prerequisites

- S-02 (`draft-authoring-persistence`) — draft content and editor exist
- F-01 (`review-quality-checks`) — output meets section-gap and actionability guardrails

## PRD references

- US-01, FR-007, FR-008, FR-010, FR-011, FR-012

## Open question

Will "no visible progress" during AI review cause mass tab closures? (Owner: user; may promote FR-014 post-pilot.)

## Risks

Highest-value capability and the product wedge made real. Sequenced as soon as drafts and quality checks exist so the core loop reaches the north star fast.

## Definition of done

- [ ] User can click "Publish for review" from `draft` → ADR enters `in_review`
- [ ] Editing disabled while `in_review`
- [ ] AI review completes and ADR transitions to `after_review`
- [ ] User sees actionable annotations for missing sections, inconsistencies, and conciseness
- [ ] Review output passes F-01 quality checks on representative fixtures
- [ ] Review runs once per ADR (no re-review on later edits)

## Planning

Run `/plan first-ai-review-annotations` after S-02 and F-01 are merged.
```

---

## Issue 6 — S-05: Publish After Review (North Star)

| Field | Value |
|---|---|
| **Title** | Let users edit reviewed ADRs and publish them as proposed |
| **Labels** | `roadmap`, `slice`, `stream-a`, `north-star` |
| **Milestone** | MVP — Core loop |
| **Roadmap ID** | S-05 |
| **Change ID** | `publish-after-review` |
| **Ready for `/plan`** | no (requires S-04) |
| **Blocked by** | S-04 (#TBD) |

### Body

```markdown
## Summary

**North star slice** — completes Success Criterion #1: the full one-session flow `draft` → `in_review` → `after_review` → `proposed`.

**Outcome:** User can edit the reviewed ADR without re-triggering review and publish it as `proposed`.

## User stories

- **US-01** (completion): full flow through publish as `proposed`
- **US-04:** Edit in `after_review` without re-review; publish transitions to `proposed`

## Functional requirements

- **FR-005:** Edit markdown in `after_review` (editing allowed; not in `in_review`)
- **FR-007:** Status transition `after_review` → `proposed`
- **FR-009:** "Publish" from `after_review` does not trigger AI re-review

## Acceptance criteria (from US-01 / US-04)

- Editing in `after_review` does **not** trigger another AI review
- Changes are preserved; status does not revert to `draft` or `in_review`
- Clicking "Publish" from `after_review` transitions ADR to `proposed`

## Prerequisites

- S-04 (`first-ai-review-annotations`) — user reaches `after_review` with annotations

## PRD references

- US-01, US-04, FR-005, FR-007, FR-009

## Risks

Without this slice, review feedback never becomes a publishable ADR and Success Criterion #1 stays unmet. If this loop does not work end to end, nothing else in the product matters.

## Definition of done

- [ ] User can edit ADR markdown inline in `after_review`
- [ ] Edits persist (save-on-blur / save-on-unload)
- [ ] Status remains `after_review` during edits (no re-review, no revert)
- [ ] User can click "Publish" → ADR becomes `proposed`
- [ ] End-to-end demo: login → new ADR → draft → review → fix → publish as `proposed`

## Planning

Run `/plan publish-after-review` after S-04 is merged.
```

---

## Issue 7 — S-03: ADR History Cards

| Field | Value |
|---|---|
| **Title** | Let users browse ADR history cards and reopen existing ADRs |
| **Labels** | `roadmap`, `slice`, `stream-c` |
| **Milestone** | MVP — History |
| **Roadmap ID** | S-03 |
| **Change ID** | `adr-history-cards` |
| **Ready for `/plan`** | no (requires S-02) |
| **Blocked by** | S-02 (#TBD) |

### Body

```markdown
## Summary

Vertical slice: card-based ADR history so users can return later and reopen documents.

**Outcome:** User can return later, browse owned ADR cards (title, status, last-edited), and reopen an existing ADR where editing is allowed.

## User story

**US-02:** Given a logged-in user with ADRs from a previous session, when they open their ADR list, then they see all owned ADRs across statuses with clear indicators and can open any for viewing/editing where permitted.

## Functional requirements

- **FR-013:** Card view showing at minimum title, current status, and last edited timestamp
- Open ADR for viewing; editing where status allows (per FR-005)

## Prerequisites

- S-02 (`draft-authoring-persistence`) — ADRs exist to list

## PRD references

- US-02, FR-013
- NFR: Data retention

## Risks

Proves Secondary success criterion (lasting value), but under `speed` follows the core loop — empty history has nothing meaningful to show until drafts exist. Can parallel S-04/S-05 after S-02.

## Definition of done

- [ ] Logged-in user sees card list of all their ADRs (all four statuses)
- [ ] Each card shows title, status, and last-edited timestamp
- [ ] User can open an ADR from a card
- [ ] Editing behavior respects status rules (no edit in `in_review`)

## Planning

Run `/plan adr-history-cards` after S-02 is merged.
```

---

## Issue 8 — S-06: Remove ADR From Active List

| Field | Value |
|---|---|
| **Title** | Let users remove ADRs from the active card view |
| **Labels** | `roadmap`, `slice`, `stream-c` |
| **Milestone** | MVP — History |
| **Roadmap ID** | S-06 |
| **Change ID** | `remove-adr-from-active-list` |
| **Ready for `/plan`** | no (requires S-03) |
| **Blocked by** | S-03 (#TBD) |

### Body

```markdown
## Summary

Vertical slice: soft-delete ADRs from the active card list while retaining records.

**Outcome:** User can remove an ADR from the active card view while the record remains retained (soft-delete).

## Functional requirements

- **FR-015:** User can remove their own ADR from the active list; removed ADRs no longer appear in card view; permanent destruction is out of MVP scope

## Prerequisites

- S-03 (`adr-history-cards`) — active card list exists
- F-02 soft-delete flag — exercised here through real user behavior

## PRD references

- FR-015
- NFR: Data retention

## Risks

Removal only has user value once an active card list exists; sequenced last under `speed`.

## Definition of done

- [ ] User can remove an ADR from the card view
- [ ] Removed ADR no longer appears in active list
- [ ] Record retained in DB (soft-delete); no permanent destroy action in UI
- [ ] User cannot access removed ADR through normal navigation (direct link behavior TBD in plan)

## Planning

Run `/plan remove-adr-from-active-list` after S-03 is merged.
```

---

## Suggested milestones (create manually if missing)

### MVP — Core loop

F-02, F-01, S-01, S-02, S-04, S-05 — delivers north star S-05.

### MVP — History

S-03, S-06 — secondary success criterion and lifecycle cleanup.

---

## Creation checklist (when you are ready)

1. Review titles and bodies above; adjust scope or acceptance criteria if needed.
2. Create labels: `roadmap`, `foundation`, `slice`, `stream-a`, `stream-b`, `stream-c`, `north-star`.
3. Create milestones: `MVP — Core loop`, `MVP — History`.
4. Create issues **in dependency order** so `#TBD` placeholders can be replaced with real numbers:
   1. F-02
   2. F-01 (parallel)
   3. S-01
   4. S-02
   5. S-04
   6. S-05
   7. S-03 (can parallel S-04/S-05 after S-02)
   8. S-06
5. Link blocked-by relationships in GitHub after all issues exist.

### Example `gh` commands (do not run until approved)

Replace `#NNN` with actual issue numbers after each create.

```bash
# 1 — F-02 (no blockers)
gh issue create \
  --title "Add Postgres driver, migrations, and initial User/ADR schema" \
  --label "roadmap,foundation,stream-a" \
  --milestone "MVP — Core loop" \
  --body-file context/changes/roadmap-github-issues-proposal.md  # extract F-02 body section

# 2 — F-01 (parallel, no blockers)
gh issue create \
  --title "Add review-quality checks for required-section and actionability guardrails" \
  --label "roadmap,foundation,stream-b" \
  --milestone "MVP — Core loop"

# 3 — S-01 (blocked by F-02)
gh issue create \
  --title "Let users register, log in, and reach a protected ADR workspace" \
  --label "roadmap,slice,stream-a" \
  --milestone "MVP — Core loop"
# then: gh issue edit <S-01-num> --add-label "blocked" && link blocked-by F-02 in UI

# … repeat for S-02 through S-06
```

> **Tip:** For cleaner `gh issue create --body-file`, split each issue body into `context/changes/github-issues/<change-id>.md` when you are ready to push — this proposal keeps everything in one reviewable document.

---

## Not included (parked in roadmap)

These remain in `roadmap.md` § Parked — no GitHub issues proposed:

- Email notification on review complete (FR-014)
- Password reset
- Re-review, export, team features, filtering/search, accepted/superseded statuses, etc.

See `context/foundation/roadmap.md` § Parked for full list.
