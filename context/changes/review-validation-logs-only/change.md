---
change_id: review-validation-logs-only
title: Review validation logs only
status: superseded
created: 2026-06-19
updated: 2026-07-04
archived_at: null
---

## Notes

Superseded by `adr-validation-re-shape` (R-01). The logs-only gate — completing reviews with invalid LLM output after logging validation failures — is replaced by a three-phase pipeline with deterministic static gap detection, parallel per-section ratings, and strict merge validation that fails the review on any validation error.
