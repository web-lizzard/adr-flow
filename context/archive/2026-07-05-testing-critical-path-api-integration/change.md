---
change_id: testing-critical-path-api-integration
title: Critical-path API integration tests (IDOR + persistence)
status: archived
created: 2026-07-05
updated: 2026-07-13
archived_at: 2026-07-13T01:03:06Z
---

## Notes

Open a change folder for rollout Phase 1 of context/foundation/test-plan.md: "Critical-path API integration".

Risks covered: #3 (IDOR — User A cannot read/modify User B's ADR), #4 backend path (persistence API round-trips).

Test types planned: API integration (pytest + httpx AsyncClient).

Risk response intent:
- Risk #3: prove User A's token cannot fetch, patch, save, delete, review, or retry User B's ADR; challenge "authenticated = authorized" on mutating routes; avoid testing only unauthenticated 401 or read-path IDOR.
- Risk #4 (backend): prove content persists via API after save; challenge "save endpoint works so draft loss is impossible"; avoid testing API save without verifying persistence round-trip at integration layer.
