---
change_id: testing-quality-gates-wiring
title: Quality gates wiring (Phase 4 test rollout)
status: implemented
created: 2026-07-13
updated: 2026-07-13
research: research.md
archived_at: null
---

## Notes

Rollout Phase 4 of context/foundation/test-plan.md: "Quality gates wiring".
Risks covered: all (1–5). Test types planned: CI/hook configuration.

Risk response intent:
- Risk #1: CI must run review-contract tests so garbage/empty ratings cannot ship undetected.
- Risk #2: CI must run failure→review_failed→retry recovery tests so stuck-in_review regressions surface on every PR.
- Risk #3: CI must run mutating IDOR denial tests so cross-user access regressions block merge.
- Risk #4: CI must run persistence round-trip and frontend persistence tests so draft-loss regressions surface before deploy.
- Risk #5: CI must run retry idempotency tests so double-retry/event duplication cannot slip through.
