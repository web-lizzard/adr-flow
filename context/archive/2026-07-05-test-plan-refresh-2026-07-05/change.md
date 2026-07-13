---
change_id: test-plan-refresh-2026-07-05
title: Refresh test-plan guide for 2026-07-05 product and test-base changes
status: archived
created: 2026-07-05
updated: 2026-07-13
archived_at: 2026-07-13T01:01:51Z
---

## Notes

Refresh `context/foundation/test-plan.md` after product and test-base drift.

**Trigger:** Product requirements changed (strict validation descoped → LLM rating system); test base grew from sparse to meaningful (57 backend + 14 frontend test files); original §3 phases are stale (Phase 1 folder missing, unit test coverage already exists).

**Refresh brief:**
- 5 refreshed risks (down from 7): LLM garbage ratings, stuck-in-review, IDOR, persistence loss, retry corruption
- 4 rollout phases: (1) Critical-path API integration, (2) AI review contract + error recovery, (3) E2E auth + north-star review with mocked LLM, (4) Quality gates wiring
- Negative space: no real-LLM e2e, no snapshots, no F-score eval, no full browser e2e for every transition
- Test-base profile update: sparse → meaningful
- User's north star: the review process works end-to-end; auth e2e also required
