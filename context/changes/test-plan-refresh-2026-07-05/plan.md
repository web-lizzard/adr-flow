# Plan: Refresh test-plan guide (2026-07-05)

## Goal

Rewrite `context/foundation/test-plan.md` to reflect product pivot (LLM rating system), meaningful test base (~67 files), and reset rollout phases per `research.md`.

## Progress

- [x] 1. Synthesize refresh brief from research + user constraints (5 risks, 4 phases, negative space, north star)
- [x] 2. Rewrite `context/foundation/test-plan.md` (§1–§8, version 2 header, reset §3 statuses)
- [ ] 3. Open Phase 1 rollout change folder and begin `/research` → `/plan` → `/implement` chain

## Out of scope (this change)

- Writing new tests (lands in rollout Phase 1+ change folders)
- CI/hook wiring (Phase 4)
- Product change to hard-fail garbage LLM ratings (noted as open question in research)

## Verification

- Guide cites evidence-only sources in §2 (no file anchors)
- `test_base_profile` updated to meaningful
- §3 phases reset to `not started` with no stale change folder
- §7 includes refresh negative-space items (no real-LLM e2e, no F-score, etc.)
