---
change_id: testing-ai-review-contract-error-recovery
title: AI review contract and error recovery tests
status: archived
created: 2026-07-05
updated: 2026-07-13
archived_at: 2026-07-13T01:02:37Z
---

## Notes

Open a change folder for rollout Phase 2 of context/foundation/test-plan.md: "AI review contract + error recovery".

Risks covered: #1 (garbage/empty section ratings erode trust), #2 (ADR stuck in in_review after worker failure), #5 (retry corrupts state / duplicate events).

Test types planned: Integration (fake LLM injection, handler failure, retry idempotency).

Risk response intent:
- Risk #1: prove merged API review output always has five section ratings (0–5) with valid annotations; malformed LLM payloads cannot silently complete as empty after_review; challenge "schema validation exists so ratings are always good"; avoid oracle copied from implementation or exact LLM wording.
- Risk #2: prove handler failure transitions ADR to review_failed with persisted review_error, and user retry clears error and returns to in_review; challenge "TaskGroup catches exceptions"; avoid happy-path-only review tests.
- Risk #5: prove retry from review_failed is idempotent; double retry or concurrent submit does not duplicate events or leave stale review_error; challenge "retry endpoint returns 200 so state is correct"; avoid testing only single happy retry.
