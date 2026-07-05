---
change_id: conditional-adr-re-review
title: Let users request one re-review when first review found errors
status: archived
created: 2026-06-19
updated: 2026-07-05
archived_at: 2026-07-05T01:15:00Z
---

## Notes

Cancelled — not implementing. With static gap detection, per-section ratings, and error-status (reviews always complete to `after_review`), the user already decides next steps from ratings and annotations. The original S-09 trigger (`non-empty actionable annotations`) would match almost every ADR; a meaningful eligibility predicate was never resolved. PRD non-goal "review once" stands.
